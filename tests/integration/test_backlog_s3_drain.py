"""Integration tests for draining the backlog to a local S3 server."""

from pathlib import Path
from time import monotonic, sleep
from typing import Any

import pytest

from OTCamera.config import S3Config
from OTCamera.controller import backlog_worker as backlog_worker_module
from OTCamera.controller.backlog import UploadBacklog
from OTCamera.controller.upload_backlog_controller import UploadBacklogController
from OTCamera.domain.events import EventBus, RecordingSplit, S3FileUploaded
from OTCamera.plugin.upload.s3_upload import S3Upload
from tests.integration.conftest import KEY_PREFIX, body_of, keys_in_bucket

_SEGMENT_TIMESTAMPS = (
    "2026-08-12_10-00-00",
    "2026-08-12_10-01-00",
    "2026-08-12_10-02-00",
)

_DRAIN_TIMEOUT_SECONDS = 20.0


@pytest.fixture
def video_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "videos"
    directory.mkdir()
    return directory


@pytest.fixture
def backlog(video_dir: Path) -> UploadBacklog:
    return UploadBacklog(video_dir=video_dir, video_format="h264", min_free_bytes=0)


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def upload(s3client: Any, local_s3_config: S3Config) -> S3Upload:
    return S3Upload(s3client, bucket_name=local_s3_config.bucket, key_prefix=KEY_PREFIX)


def _content_of(name: str) -> bytes:
    """Return the bytes a segment with this name was recorded with."""
    return f"video recorded as {name}".encode()


def _record(event_bus: EventBus, video_dir: Path, timestamp: str) -> str:
    """Record one finished segment and announce it, returning its filename."""
    name = f"otcamera_FR20_{timestamp}.h264"
    segment = video_dir / name
    segment.write_bytes(_content_of(name))
    event_bus.publish(RecordingSplit(str(segment)))
    return name


def _key(name: str) -> str:
    return f"{KEY_PREFIX}/{name}"


@pytest.mark.integration
def test_a_pass_uploads_the_oldest_segment_first(
    reset_s3_bucket: Any,
    s3client: Any,
    local_s3_config: S3Config,
    event_bus: EventBus,
    backlog: UploadBacklog,
    video_dir: Path,
    upload: S3Upload,
) -> None:
    controller = UploadBacklogController(event_bus, upload, backlog, None)
    names = [
        _record(event_bus, video_dir, timestamp)
        for timestamp in reversed(_SEGMENT_TIMESTAMPS)
    ]
    oldest = min(names)

    controller.run_once()

    assert keys_in_bucket(s3client, local_s3_config.bucket) == {_key(oldest)}
    assert backlog.size() == len(names) - 1
    assert not (backlog.pending / oldest).exists()


@pytest.mark.integration
def test_the_uploaded_event_names_the_bucket_and_key(
    reset_s3_bucket: Any,
    local_s3_config: S3Config,
    event_bus: EventBus,
    backlog: UploadBacklog,
    video_dir: Path,
    upload: S3Upload,
) -> None:
    controller = UploadBacklogController(event_bus, upload, backlog, None)
    received: list[S3FileUploaded] = []
    event_bus.subscribe(S3FileUploaded, received.append)
    name = _record(event_bus, video_dir, _SEGMENT_TIMESTAMPS[0])

    controller.run_once()
    event_bus.process_pending()

    assert [(event.bucket, event.key) for event in received] == [
        (local_s3_config.bucket, _key(name))
    ]
    assert received[0].local_path == backlog.pending / name


@pytest.mark.integration
def test_segments_survive_an_outage_and_drain_when_the_server_returns(
    missing_s3_bucket: None,
    s3client: Any,
    local_s3_config: S3Config,
    event_bus: EventBus,
    backlog: UploadBacklog,
    video_dir: Path,
    upload: S3Upload,
) -> None:
    controller = UploadBacklogController(event_bus, upload, backlog, None)
    names = [
        _record(event_bus, video_dir, timestamp) for timestamp in _SEGMENT_TIMESTAMPS
    ]

    for _ in names:
        controller.run_once()

    assert backlog.size() == len(names)
    assert backlog.uploaded_total == 0
    assert controller.wait_seconds > 5.0, "expected the worker to back off"

    s3client.create_bucket(Bucket=local_s3_config.bucket)
    for _ in names:
        controller.run_once()

    assert backlog.size() == 0
    assert backlog.uploaded_total == len(names)
    assert keys_in_bucket(s3client, local_s3_config.bucket) == {
        _key(name) for name in names
    }


@pytest.mark.integration
def test_a_segment_the_server_rejects_blocks_the_ones_behind_it(
    reset_s3_bucket: Any,
    s3client: Any,
    local_s3_config: S3Config,
    event_bus: EventBus,
    backlog: UploadBacklog,
    video_dir: Path,
    upload: S3Upload,
) -> None:
    controller = UploadBacklogController(event_bus, upload, backlog, None)
    oldest = _record(event_bus, video_dir, _SEGMENT_TIMESTAMPS[0])
    newer = _record(event_bus, video_dir, _SEGMENT_TIMESTAMPS[1])
    # A segment that cannot be read stands in for one the server will never
    # accept: every pass fails on it again.
    (backlog.pending / oldest).chmod(0o000)

    try:
        for _ in range(3):
            controller.run_once()

        assert keys_in_bucket(s3client, local_s3_config.bucket) == set()
        assert backlog.size() == 2
    finally:
        (backlog.pending / oldest).chmod(0o644)

    controller.run_once()
    controller.run_once()

    assert backlog.size() == 0
    assert keys_in_bucket(s3client, local_s3_config.bucket) == {
        _key(oldest),
        _key(newer),
    }


@pytest.mark.integration
def test_the_worker_thread_drains_the_backlog_on_its_own(
    reset_s3_bucket: Any,
    s3client: Any,
    local_s3_config: S3Config,
    event_bus: EventBus,
    backlog: UploadBacklog,
    video_dir: Path,
    upload: S3Upload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Shorten the waits between passes; the interval itself is unit-tested, and
    # the point here is that the worker really moves the files to the server.
    monkeypatch.setattr(backlog_worker_module, "_IDLE_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(backlog_worker_module, "_INITIAL_WAIT_SECONDS", 0.05)
    controller = UploadBacklogController(event_bus, upload, backlog, None)
    names = [
        _record(event_bus, video_dir, timestamp) for timestamp in _SEGMENT_TIMESTAMPS
    ]

    controller.start()
    try:
        deadline = monotonic() + _DRAIN_TIMEOUT_SECONDS
        while backlog.size() > 0 and monotonic() < deadline:
            sleep(0.05)
    finally:
        controller.close()

    assert not controller.is_running
    assert backlog.size() == 0
    assert backlog.uploaded_total == len(names)
    assert keys_in_bucket(s3client, local_s3_config.bucket) == {
        _key(name) for name in names
    }
    for name in names:
        assert body_of(s3client, local_s3_config.bucket, _key(name)) == _content_of(
            name
        )
