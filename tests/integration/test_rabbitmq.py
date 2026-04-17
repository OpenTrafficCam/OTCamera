"""Integration test for RabbitMQ notification after file upload."""

import json
from pathlib import Path
from typing import Generator

import pika
import pika.adapters.blocking_connection
import pika.exchange_type
import pytest

from OTCamera.config import RabbitMqConfig
from OTCamera.controller.rabbitmq_controller import RabbitMqController
from OTCamera.domain.events import EventBus, FileUploaded
from OTCamera.plugin.rabbitmq.rabbitmq_publisher import RabbitMqPublisher

EXCHANGE = "test_otcamera"
ROUTING_KEY = "file_uploaded"
QUEUE = "test_otcamera_queue"

FILENAMES = ["/videos/clip_001.h264", "/videos/clip_002.h264"]


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
    RabbitMqController(event_bus, RabbitMqPublisher(local_rabbitmq_config))

    for filename in FILENAMES:
        event_bus.publish(FileUploaded(filename=filename))

    received = []
    for _ in FILENAMES:
        method, _, body = rabbitmq_channel.basic_get(queue=QUEUE, auto_ack=True)
        assert (
            method is not None and body is not None
        ), "Expected a message but queue was empty"
        received.append(json.loads(body))

    expected = {Path(f).name for f in FILENAMES}
    assert {msg["filename"] for msg in received} == expected
