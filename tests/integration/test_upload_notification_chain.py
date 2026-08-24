"""Integration tests for the chain from a finished segment to its notification."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pika
import pika.adapters.blocking_connection
import pytest

from OTCamera.config import OTCloudSettings, RabbitMqConfig, S3Config
from OTCamera.controller.backlog import NotificationBacklog, UploadBacklog
from OTCamera.controller.backlog_controller import BacklogController
from OTCamera.controller.notification_backlog_controller import (
    NotificationBacklogController,
)
from OTCamera.domain.events import EventBus, RecordingSplit
from OTCamera.plugin.upload.s3_upload import S3Upload
from OTCamera.plugin.upload_notifier.payload_factories import (
    RabbitMQS3UploadToOTCloudPayloadFactory,
)
from OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier import RabbitNotifier
from tests.integration.conftest import (
    KEY_PREFIX,
    closed_port,
    keys_in_bucket,
    messages_in_queue,
)

_SEGMENT_TIMESTAMPS = ("2026-08-12_10-00-00", "2026-08-12_10-01-00")

_GIB = 1024 * 1024 * 1024

OT_CLOUD = OTCloudSettings(camera_id=2, project_id=0, site_id=1)


@pytest.fixture
def video_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "videos"
    directory.mkdir()
    return directory


@pytest.fixture
def upload_backlog(video_dir: Path) -> UploadBacklog:
    return UploadBacklog(video_dir=video_dir, video_format="h264", min_free_bytes=0)


@pytest.fixture
def notification_backlog(
    upload_backlog: UploadBacklog, video_dir: Path
) -> NotificationBacklog:
    return NotificationBacklog(video_dir=video_dir, min_free_bytes=0)


@pytest.fixture
def upload(s3client: Any, local_s3_config: S3Config) -> S3Upload:
    return S3Upload(s3client, bucket_name=local_s3_config.bucket, key_prefix=KEY_PREFIX)


def _record(event_bus: EventBus, video_dir: Path, timestamp: str) -> str:
    """Record one finished segment and announce it, returning its filename."""
    name = f"otcamera_FR20_{timestamp}.h264"
    segment = video_dir / name
    segment.write_bytes(f"video recorded as {name}".encode())
    event_bus.publish(RecordingSplit(str(segment)))
    return name


def _notification_controller(
    backlog: NotificationBacklog, upload: S3Upload, config: RabbitMqConfig
) -> NotificationBacklogController:
    return NotificationBacklogController(
        backlog=backlog,
        upload=upload,
        notifier=RabbitNotifier(config),
        payload_factory=RabbitMQS3UploadToOTCloudPayloadFactory(OT_CLOUD),
    )


@pytest.mark.integration
def test_a_segment_leaves_the_card_only_once_it_is_uploaded_and_announced(
    reset_s3_bucket: Any,
    s3client: Any,
    local_s3_config: S3Config,
    local_rabbitmq_config: RabbitMqConfig,
    rabbitmq_channel: pika.adapters.blocking_connection.BlockingChannel,
    upload_backlog: UploadBacklog,
    notification_backlog: NotificationBacklog,
    video_dir: Path,
    upload: S3Upload,
) -> None:
    event_bus = EventBus()
    uploader = BacklogController(
        event_bus, upload, upload_backlog, notification_backlog
    )
    announcer = _notification_controller(
        notification_backlog, upload, local_rabbitmq_config
    )
    names = [
        _record(event_bus, video_dir, timestamp) for timestamp in _SEGMENT_TIMESTAMPS
    ]

    for _ in names:
        uploader.run_once()

    assert keys_in_bucket(s3client, local_s3_config.bucket) == {
        f"{KEY_PREFIX}/{name}" for name in names
    }
    assert upload_backlog.size() == 0
    assert notification_backlog.size() == len(names), (
        "An uploaded segment has to wait until it has been announced"
    )

    announcer.run_once()
    announcer.close()

    received = messages_in_queue(rabbitmq_channel, len(names))
    assert [message["s3_key"] for message in received] == [
        f"{KEY_PREFIX}/{name}" for name in names
    ]
    assert notification_backlog.size() == 0
    assert notification_backlog.notified_total == len(names)


@pytest.mark.integration
def test_an_unreachable_broker_keeps_every_segment_for_a_later_run(
    reset_s3_bucket: Any,
    local_rabbitmq_config: RabbitMqConfig,
    rabbitmq_channel: pika.adapters.blocking_connection.BlockingChannel,
    upload_backlog: UploadBacklog,
    notification_backlog: NotificationBacklog,
    video_dir: Path,
    upload: S3Upload,
) -> None:
    """The segments outlive the outage and are announced by a later run.

    The second controller is a fresh one over the same directory, the way the
    camera picks up what an earlier run left behind after a restart.
    """
    event_bus = EventBus()
    uploader = BacklogController(
        event_bus, upload, upload_backlog, notification_backlog
    )
    names = [
        _record(event_bus, video_dir, timestamp) for timestamp in _SEGMENT_TIMESTAMPS
    ]
    for _ in names:
        uploader.run_once()

    offline_config = local_rabbitmq_config.model_copy(update={"port": closed_port()})
    offline = _notification_controller(notification_backlog, upload, offline_config)
    offline.run_once()
    offline.close()

    assert notification_backlog.size() == len(names)
    waiting = rabbitmq_channel.basic_get(queue=local_rabbitmq_config.queue_name)
    assert waiting[0] is None, "Nothing may reach the broker while it is unreachable"

    recovered = NotificationBacklog(video_dir=video_dir, min_free_bytes=0)
    announcer = _notification_controller(recovered, upload, local_rabbitmq_config)
    announcer.run_once()
    announcer.close()

    received = messages_in_queue(rabbitmq_channel, len(names))
    assert [message["original_filename"] for message in received] == names
    assert recovered.size() == 0


@pytest.mark.integration
def test_a_full_card_costs_notifications_before_it_costs_footage(
    reset_s3_bucket: Any,
    s3client: Any,
    local_s3_config: S3Config,
    local_rabbitmq_config: RabbitMqConfig,
    rabbitmq_channel: pika.adapters.blocking_connection.BlockingChannel,
    video_dir: Path,
    upload: S3Upload,
) -> None:
    """The store holding uploaded segments gives up its files first."""
    upload_backlog = UploadBacklog(
        video_dir=video_dir, video_format="h264", min_free_bytes=_GIB
    )
    notification_backlog = NotificationBacklog(
        video_dir=video_dir, min_free_bytes=2 * _GIB
    )
    event_bus = EventBus()
    uploader = BacklogController(
        event_bus, upload, upload_backlog, notification_backlog
    )
    announcer = _notification_controller(
        notification_backlog, upload, local_rabbitmq_config
    )

    announced_never = _record(event_bus, video_dir, "2026-08-12_10-00-00")
    uploader.run_once()
    assert notification_backlog.size() == 1
    recorded_later = _record(event_bus, video_dir, "2026-08-12_10-01-00")

    # free space between the two floors: the notifications are in reach of
    # being given up, the footage is not.
    with patch(
        "OTCamera.controller.backlog.psutil.disk_usage",
        return_value=SimpleNamespace(free=int(1.5 * _GIB)),
    ):
        announcer.run_once()
        uploader.run_once()
    announcer.close()

    assert notification_backlog.dropped_total == 1, (
        "the segment waiting to be announced pays for the space"
    )
    assert upload_backlog.dropped_total == 0, "no footage is dropped while it can"
    assert rabbitmq_channel.basic_get(queue=local_rabbitmq_config.queue_name)[0] is None

    # both segments still reached the server; only the message about the first
    # one was given up.
    assert keys_in_bucket(s3client, local_s3_config.bucket) == {
        f"{KEY_PREFIX}/{announced_never}",
        f"{KEY_PREFIX}/{recorded_later}",
    }
    assert notification_backlog.size() == 1, (
        "the segment recorded later was handed over, not dropped"
    )
