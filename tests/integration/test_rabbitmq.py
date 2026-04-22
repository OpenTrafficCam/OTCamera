"""Integration test for RabbitMQ notification after file upload."""

import json
from datetime import datetime, timezone
from typing import Generator

import pika
import pika.adapters.blocking_connection
import pika.exchange_type
import pytest

from OTCamera.config import OTCloudSettings, RabbitMqConfig
from OTCamera.controller.notification_controller import (
    EventNotificationController,
)
from OTCamera.domain.events import EventBus, S3FileUploaded
from OTCamera.plugin.upload_notifier.rabbitmq_s3_upload_to_otcloud import (
    RabbitMQS3UploadToOTCloudPayloadFactory,
)
from OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier import RabbitNotifier

EXCHANGE = "test_otcamera"
ROUTING_KEY = "file_uploaded"
QUEUE = "test_otcamera_queue"

FILES = [
    {
        "local_path": "/videos/clip_001.h264",
        "key": "camera1/clip_001.h264",
        "bucket": "my-bucket",
    },
    {
        "local_path": "/videos/clip_002.h264",
        "key": "camera1/clip_002.h264",
        "bucket": "my-bucket",
    },
]

OT_CLOUD = OTCloudSettings(camera_id=2, project_id=0, site_id=1)


@pytest.fixture
def local_rabbitmq_config() -> RabbitMqConfig:
    return RabbitMqConfig(
        host="127.0.0.1",
        exchange=EXCHANGE,
        routing_key=ROUTING_KEY,
        durable=False,
    )


@pytest.fixture
def rabbitmq_channel(
    local_rabbitmq_config: RabbitMqConfig,
) -> Generator[pika.adapters.blocking_connection.BlockingChannel, None, None]:
    """Yield a channel with a bound queue; clean up after the test."""
    credentials = pika.PlainCredentials(
        local_rabbitmq_config.user, local_rabbitmq_config.password
    )
    parameters = pika.ConnectionParameters(
        host=local_rabbitmq_config.host,
        port=local_rabbitmq_config.port,
        virtual_host=local_rabbitmq_config.vhost,
        credentials=credentials,
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.exchange_declare(
        exchange=EXCHANGE,
        exchange_type=pika.exchange_type.ExchangeType.direct,
        durable=False,
    )
    channel.queue_declare(queue=QUEUE, durable=False)
    channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key=ROUTING_KEY)

    yield channel

    channel.queue_delete(queue=QUEUE)
    channel.exchange_delete(exchange=EXCHANGE)
    connection.close()


@pytest.mark.integration
def test_rabbitmq_notification(
    rabbitmq_channel: pika.adapters.blocking_connection.BlockingChannel,
    local_rabbitmq_config: RabbitMqConfig,
) -> None:
    event_bus = EventBus()
    EventNotificationController(
        event_bus,
        S3FileUploaded,
        RabbitNotifier(local_rabbitmq_config),
        RabbitMQS3UploadToOTCloudPayloadFactory(OT_CLOUD),
    )

    ts = datetime.now(tz=timezone.utc)
    for f in FILES:
        event_bus.publish(
            S3FileUploaded(
                filename=f["local_path"],
                timestamp=ts,
                bucket=f["bucket"],
                key=f["key"],
                original_filename=f["local_path"].split("/")[-1],
            )
        )

    received = []
    for _ in FILES:
        method, _, body = rabbitmq_channel.basic_get(queue=QUEUE, auto_ack=True)
        assert (
            method is not None and body is not None
        ), "Expected a message but queue was empty"
        received.append(json.loads(body))

    assert {msg["s3_key"] for msg in received} == {f["key"] for f in FILES}
    assert {msg["original_filename"] for msg in received} == {
        f["local_path"] for f in FILES
    }
    assert {msg["bucket_name"] for msg in received} == {"my-bucket"}
    assert all(
        msg["camera_id"] == {"camera_id": 2, "project_id": 0, "site_id": 1}
        for msg in received
    )
