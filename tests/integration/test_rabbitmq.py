"""Integration test for RabbitMQ notification after file upload."""

from pathlib import Path

import pika
import pika.adapters.blocking_connection
import pytest

from OTCamera.config import OTCloudSettings, RabbitMqConfig
from OTCamera.domain.upload import S3UploadResult
from OTCamera.plugin.upload_notifier.payload_factories import (
    RabbitMQS3UploadToOTCloudPayloadFactory,
)
from OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier import RabbitNotifier
from tests.integration.conftest import messages_in_queue

FILES = [
    {
        "local_path": "/videos/otcamera_FR20_2026-08-12_10-00-00.h264",
        "key": "camera1/otcamera_FR20_2026-08-12_10-00-00.h264",
        "bucket": "my-bucket",
    },
    {
        "local_path": "/videos/otcamera_FR20_2026-08-12_10-15-00.h264",
        "key": "camera1/otcamera_FR20_2026-08-12_10-15-00.h264",
        "bucket": "my-bucket",
    },
]

OT_CLOUD = OTCloudSettings(camera_id=2, project_id=0, site_id=1)


@pytest.mark.integration
def test_rabbitmq_notification(
    rabbitmq_channel: pika.adapters.blocking_connection.BlockingChannel,
    local_rabbitmq_config: RabbitMqConfig,
) -> None:
    notifier = RabbitNotifier(local_rabbitmq_config)
    factory = RabbitMQS3UploadToOTCloudPayloadFactory(OT_CLOUD)

    for f in FILES:
        notifier.notify(
            factory.create(
                S3UploadResult(
                    local_path=Path(f["local_path"]),
                    bucket=f["bucket"],
                    key=f["key"],
                )
            )
        )

    notifier.close()

    received = messages_in_queue(rabbitmq_channel, len(FILES))

    assert {msg["s3_key"] for msg in received} == {f["key"] for f in FILES}
    assert {msg["original_filename"] for msg in received} == {
        Path(f["local_path"]).name for f in FILES
    }
    assert {msg["bucket_name"] for msg in received} == {"my-bucket"}
    assert all(
        msg["camera_id"] == {"camera_id": 2, "project_id": 0, "site_id": 1}
        for msg in received
    )
    assert {msg["timestamp"] for msg in received} == {"1970-01-01T00:00:00+00:00"}
