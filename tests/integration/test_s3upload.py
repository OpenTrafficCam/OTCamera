"""Integration tests for the S3 upload backend against a local S3 server."""

from pathlib import Path
from shutil import copyfile
from typing import Any

import pytest

from OTCamera.config import S3Config
from OTCamera.controller.backlog import UploadBacklog
from OTCamera.controller.backlog_controller import BacklogController
from OTCamera.domain.events import EventBus, RecordingSplit
from OTCamera.plugin.upload.exceptions import FileUploadError
from OTCamera.plugin.upload.s3_upload import S3Upload
from tests.integration.conftest import (
    EXAMPLE_VIDEOS_PATHS,
    KEY_PREFIX,
    body_of,
    keys_in_bucket,
    make_s3client,
)


def _recorded_segment(video_dir: Path, name: str, content: bytes) -> Path:
    segment = video_dir / name
    segment.write_bytes(content)
    return segment


@pytest.mark.integration
def test_s3_upload(
    reset_s3_bucket: Any, s3client: Any, local_s3_config: S3Config, tmp_path: Path
) -> None:
    upload = S3Upload(
        s3client, bucket_name=local_s3_config.bucket, key_prefix=KEY_PREFIX
    )

    video_dir = tmp_path / "videos"
    video_dir.mkdir()
    backlog = UploadBacklog(video_dir=video_dir, video_format="h264", min_free_bytes=0)

    event_bus = EventBus()
    backlog_controller = BacklogController(
        event_bus=event_bus, upload=upload, backlog=backlog, notification_backlog=None
    )

    for example_video in EXAMPLE_VIDEOS_PATHS:
        recorded = video_dir / example_video.name
        copyfile(example_video, recorded)
        event_bus.publish(RecordingSplit(str(recorded)))

    assert backlog.size() == len(EXAMPLE_VIDEOS_PATHS)

    # Drain the backlog on this thread so that the assertions below cannot race
    # the worker.
    for _ in EXAMPLE_VIDEOS_PATHS:
        backlog_controller.run_once()

    assert backlog.size() == 0
    assert backlog.uploaded_total == len(EXAMPLE_VIDEOS_PATHS)

    keys = keys_in_bucket(s3client, local_s3_config.bucket)

    expected = {f"{KEY_PREFIX}/{p.name}" for p in EXAMPLE_VIDEOS_PATHS}

    assert keys == expected


class TestKeys:
    @pytest.mark.integration
    def test_the_filename_becomes_the_key_without_a_prefix(
        self, reset_s3_bucket: Any, s3client: Any, local_s3_config: S3Config
    ) -> None:
        upload = S3Upload(s3client, bucket_name=local_s3_config.bucket)
        example_video = sorted(EXAMPLE_VIDEOS_PATHS)[0]

        result = upload.upload(example_video)

        assert result.key == example_video.name
        assert result.bucket == local_s3_config.bucket
        assert result.local_path == example_video
        assert keys_in_bucket(s3client, local_s3_config.bucket) == {example_video.name}

    @pytest.mark.integration
    def test_a_prefix_with_path_segments_becomes_a_nested_key(
        self, reset_s3_bucket: Any, s3client: Any, local_s3_config: S3Config
    ) -> None:
        upload = S3Upload(
            s3client, bucket_name=local_s3_config.bucket, key_prefix=KEY_PREFIX
        )
        example_video = sorted(EXAMPLE_VIDEOS_PATHS)[0]

        result = upload.upload(example_video)

        assert result.key == f"{KEY_PREFIX}/{example_video.name}"
        assert keys_in_bucket(s3client, local_s3_config.bucket) == {result.key}


class TestStoredContent:
    @pytest.mark.integration
    def test_the_object_holds_the_bytes_that_were_recorded(
        self, reset_s3_bucket: Any, s3client: Any, local_s3_config: S3Config
    ) -> None:
        upload = S3Upload(
            s3client, bucket_name=local_s3_config.bucket, key_prefix=KEY_PREFIX
        )

        for example_video in EXAMPLE_VIDEOS_PATHS:
            result = upload.upload(example_video)

            stored = body_of(s3client, local_s3_config.bucket, result.key)
            assert stored == example_video.read_bytes()

    @pytest.mark.integration
    def test_a_segment_larger_than_one_request_arrives_whole(
        self,
        reset_s3_bucket: Any,
        s3client: Any,
        local_s3_config: S3Config,
        tmp_path: Path,
    ) -> None:
        # Multipart splitting is switched off in the backend, so a segment of
        # this size has to go over the wire in a single request.
        content = bytes(range(256)) * 40_000
        segment = _recorded_segment(
            tmp_path, "otcamera_FR20_2026-08-12_10-00-00.h264", content
        )
        upload = S3Upload(s3client, bucket_name=local_s3_config.bucket)

        result = upload.upload(segment)

        assert body_of(s3client, local_s3_config.bucket, result.key) == content

    @pytest.mark.integration
    def test_uploading_the_same_name_twice_replaces_the_object(
        self,
        reset_s3_bucket: Any,
        s3client: Any,
        local_s3_config: S3Config,
        tmp_path: Path,
    ) -> None:
        name = "otcamera_FR20_2026-08-12_10-00-00.h264"
        upload = S3Upload(s3client, bucket_name=local_s3_config.bucket)
        upload.upload(_recorded_segment(tmp_path, name, b"first attempt"))

        result = upload.upload(_recorded_segment(tmp_path, name, b"second attempt"))

        assert keys_in_bucket(s3client, local_s3_config.bucket) == {name}
        assert (
            body_of(s3client, local_s3_config.bucket, result.key) == b"second attempt"
        )


class TestFailingUploads:
    @pytest.mark.integration
    def test_a_missing_bucket_fails_the_upload(
        self, missing_s3_bucket: None, s3client: Any, local_s3_config: S3Config
    ) -> None:
        upload = S3Upload(s3client, bucket_name=local_s3_config.bucket)

        with pytest.raises(FileUploadError):
            upload.upload(sorted(EXAMPLE_VIDEOS_PATHS)[0])

    @pytest.mark.integration
    def test_an_unreachable_server_fails_the_upload(
        self, local_s3_config: S3Config
    ) -> None:
        upload = S3Upload(
            make_s3client(_unreachable(local_s3_config)),
            bucket_name=local_s3_config.bucket,
        )

        with pytest.raises(FileUploadError):
            upload.upload(sorted(EXAMPLE_VIDEOS_PATHS)[0])

    @pytest.mark.integration
    def test_a_file_that_is_not_there_fails_the_upload(
        self,
        reset_s3_bucket: Any,
        s3client: Any,
        local_s3_config: S3Config,
        tmp_path: Path,
    ) -> None:
        upload = S3Upload(s3client, bucket_name=local_s3_config.bucket)

        with pytest.raises(FileUploadError):
            upload.upload(tmp_path / "never_recorded.h264")

        assert keys_in_bucket(s3client, local_s3_config.bucket) == set()


class TestAvailability:
    @pytest.mark.integration
    def test_the_server_with_the_bucket_is_available(
        self, reset_s3_bucket: Any, s3client: Any, local_s3_config: S3Config
    ) -> None:
        upload = S3Upload(
            s3client, bucket_name=local_s3_config.bucket, key_prefix=KEY_PREFIX
        )

        assert upload.is_available()

    @pytest.mark.integration
    def test_the_check_leaves_nothing_behind(
        self, reset_s3_bucket: Any, s3client: Any, local_s3_config: S3Config
    ) -> None:
        upload = S3Upload(
            s3client, bucket_name=local_s3_config.bucket, key_prefix=KEY_PREFIX
        )

        assert upload.is_available()

        assert keys_in_bucket(s3client, local_s3_config.bucket) == set()

    @pytest.mark.integration
    def test_a_missing_bucket_is_not_available(
        self, missing_s3_bucket: None, s3client: Any, local_s3_config: S3Config
    ) -> None:
        upload = S3Upload(s3client, bucket_name=local_s3_config.bucket)

        assert not upload.is_available()

    @pytest.mark.integration
    def test_an_unreachable_server_is_not_available(
        self, local_s3_config: S3Config
    ) -> None:
        upload = S3Upload(
            make_s3client(_unreachable(local_s3_config)),
            bucket_name=local_s3_config.bucket,
        )

        assert not upload.is_available()

    @pytest.mark.integration
    def test_wrong_credentials_are_not_available(
        self, reset_s3_bucket: Any, local_s3_config: S3Config
    ) -> None:
        wrong = local_s3_config.model_copy(
            update={"access_key": "wrong", "secret_key": "wrong"}
        )
        upload = S3Upload(make_s3client(wrong), bucket_name=wrong.bucket)

        assert not upload.is_available()


def _unreachable(config: S3Config) -> S3Config:
    """Return the settings pointed at a port where no server listens.

    One attempt with a short timeout keeps the test from waiting out the
    retries the real configuration allows.
    """
    return config.model_copy(
        update={
            "endpoint_url": "http://127.0.0.1:9",
            "connect_timeout": 1,
            "read_timeout": 1,
        }
    )
