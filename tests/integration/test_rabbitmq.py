"""Integration test for RabbitMQ notification after file upload."""

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Generator

import pika
import pika.adapters.blocking_connection
import pika.exceptions
import pika.exchange_type
import pytest

from OTCamera.config import OTCloudSettings, RabbitMqConfig
from OTCamera.controller.message_store import MessageStore
from OTCamera.controller.notification_controller import EventNotificationController
from OTCamera.domain.events import EventBus, S3FileUploaded
from OTCamera.plugin.upload_notifier.payload_factories import (
    RabbitMQS3UploadToOTCloudPayloadFactory,
)
from OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier import RabbitNotifier
from OTCamera.plugin.upload_notifier.store_backed_notifier import StoreBackedNotifier

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
        host=os.getenv("OTC_TEST_RABBITMQ_HOST", "127.0.0.1"),
        port=int(os.getenv("OTC_TEST_RABBITMQ_PORT", 5672)),
        exchange=EXCHANGE,
        routing_key=ROUTING_KEY,
        queue_name=QUEUE,
        durable=False,
        ssl=False,
    )


def _connect(config: RabbitMqConfig) -> pika.BlockingConnection:
    """Open a connection the test itself uses to inspect and set up the broker."""
    credentials = pika.PlainCredentials(config.user, config.password)
    parameters = pika.ConnectionParameters(
        host=config.host,
        port=config.port,
        virtual_host=config.vhost,
        credentials=credentials,
    )
    return pika.BlockingConnection(parameters)


def _delete_exchange_and_queue(
    connection: pika.BlockingConnection, config: RabbitMqConfig
) -> None:
    """Remove the configured queue and exchange if they are still there.

    Each delete gets its own channel, because the broker closes the channel
    when it is asked for something that no longer exists. A test that
    deletes the queue itself therefore needs no special cleanup.
    """
    for delete in (
        lambda channel: channel.queue_delete(queue=config.queue_name),
        lambda channel: channel.exchange_delete(exchange=config.exchange),
    ):
        try:
            delete(connection.channel())
        except pika.exceptions.ChannelClosedByBroker:
            # already gone, which is what the cleanup wanted.
            pass


def _closed_port() -> int:
    """Return a port on localhost that nothing listens on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _upload_event(index: int) -> S3FileUploaded:
    """Build an upload event that is distinguishable from all others."""
    name = f"clip_{index:03d}.h264"
    return S3FileUploaded(
        local_path=Path("/videos") / name,
        timestamp=datetime.now(tz=timezone.utc),
        bucket="my-bucket",
        key=f"camera1/{name}",
    )


def _wait_until_delivered(store: MessageStore, timeout: float = 30.0) -> None:
    """Wait for the worker to hand every stored message over."""
    deadline = monotonic() + timeout
    while store.size() > 0 and monotonic() < deadline:
        sleep(0.05)
    assert store.size() == 0, f"{store.size()} messages were not delivered in time"


def _receive(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    count: int,
    queue: str = QUEUE,
) -> list[str]:
    """Take the given number of messages off the queue, in arrival order."""
    bodies = []
    for _ in range(count):
        method, _, body = channel.basic_get(queue=queue, auto_ack=True)
        assert method is not None and body is not None, (
            "Expected a message but queue was empty"
        )
        bodies.append(body.decode())
    return bodies


@pytest.fixture
def rabbitmq_channel(
    local_rabbitmq_config: RabbitMqConfig,
) -> Generator[pika.adapters.blocking_connection.BlockingChannel, None, None]:
    """Yield a channel with a bound queue; clean up after the test."""
    connection = _connect(local_rabbitmq_config)
    channel = connection.channel()
    channel.exchange_declare(
        exchange=EXCHANGE,
        exchange_type=pika.exchange_type.ExchangeType.direct,
        durable=False,
    )
    channel.queue_declare(queue=QUEUE, durable=False)
    channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key=ROUTING_KEY)

    yield channel

    _delete_exchange_and_queue(connection, local_rabbitmq_config)
    connection.close()


@pytest.mark.integration
def test_rabbitmq_notification(
    rabbitmq_channel: pika.adapters.blocking_connection.BlockingChannel,
    local_rabbitmq_config: RabbitMqConfig,
) -> None:
    event_bus = EventBus()
    notifier = RabbitNotifier(local_rabbitmq_config)
    controller = EventNotificationController(
        event_bus,
        S3FileUploaded,
        notifier,
        RabbitMQS3UploadToOTCloudPayloadFactory(OT_CLOUD),
    )

    ts = datetime.now(tz=timezone.utc)
    for f in FILES:
        event_bus.publish(
            S3FileUploaded(
                local_path=Path(f["local_path"]),
                timestamp=ts,
                bucket=f["bucket"],
                key=f["key"],
            )
        )

    controller.close()

    received = [json.loads(body) for body in _receive(rabbitmq_channel, len(FILES))]

    assert {msg["s3_key"] for msg in received} == {f["key"] for f in FILES}
    assert {msg["original_filename"] for msg in received} == {
        Path(f["local_path"]).name for f in FILES
    }
    assert {msg["bucket_name"] for msg in received} == {"my-bucket"}
    assert all(
        msg["camera_id"] == {"camera_id": 2, "project_id": 0, "site_id": 1}
        for msg in received
    )


@pytest.mark.integration
def test_the_store_empties_only_once_the_broker_has_the_messages(
    rabbitmq_channel: pika.adapters.blocking_connection.BlockingChannel,
    local_rabbitmq_config: RabbitMqConfig,
    tmp_path: Path,
) -> None:
    """An upload event travels from the bus to the broker, leaving nothing behind."""
    store = MessageStore(tmp_path)
    notifier = StoreBackedNotifier(RabbitNotifier(local_rabbitmq_config), store)
    notifier.start()
    event_bus = EventBus()
    controller = EventNotificationController(
        event_bus,
        S3FileUploaded,
        notifier,
        RabbitMQS3UploadToOTCloudPayloadFactory(OT_CLOUD),
    )
    events = [_upload_event(index) for index in range(5)]

    for event in events:
        event_bus.publish(event)
    _wait_until_delivered(store)
    controller.close()

    received = [json.loads(body) for body in _receive(rabbitmq_channel, len(events))]
    assert [msg["s3_key"] for msg in received] == [event.key for event in events]
    assert store.size() == 0
    assert not (tmp_path / "unreadable").exists()
    assert list((tmp_path / "incomplete").iterdir()) == []


@pytest.mark.integration
def test_an_outage_keeps_every_message_until_a_later_run_delivers_them(
    rabbitmq_channel: pika.adapters.blocking_connection.BlockingChannel,
    local_rabbitmq_config: RabbitMqConfig,
    tmp_path: Path,
) -> None:
    """Messages survive a broker that is away and go out oldest-first later.

    The second notifier is a fresh one over the same directory, the way the
    camera picks up the messages of an earlier run after a restart.
    """
    factory = RabbitMQS3UploadToOTCloudPayloadFactory(OT_CLOUD)
    payloads = [factory.create(_upload_event(index)) for index in range(5)]
    offline_config = local_rabbitmq_config.model_copy(update={"port": _closed_port()})
    offline = StoreBackedNotifier(
        RabbitNotifier(offline_config), MessageStore(tmp_path)
    )

    for payload in payloads:
        offline.notify(payload)
    offline.run_once()
    offline.close()

    assert MessageStore(tmp_path).size() == len(payloads)
    assert rabbitmq_channel.basic_get(queue=QUEUE)[0] is None, (
        "Nothing may reach the broker while it is unreachable"
    )

    store = MessageStore(tmp_path)
    recovered = StoreBackedNotifier(RabbitNotifier(local_rabbitmq_config), store)
    recovered.run_once()
    recovered.close()

    assert _receive(rabbitmq_channel, len(payloads)) == payloads
    assert store.size() == 0


@pytest.mark.integration
def test_a_message_the_broker_returns_stays_in_the_store(
    rabbitmq_channel: pika.adapters.blocking_connection.BlockingChannel,
    local_rabbitmq_config: RabbitMqConfig,
    tmp_path: Path,
) -> None:
    """A message that arrives nowhere is kept, not counted as delivered.

    The camera insists on reaching its queue, so the broker hands a message
    back once that queue is gone instead of dropping it.
    """
    store = MessageStore(tmp_path)
    notifier = StoreBackedNotifier(RabbitNotifier(local_rabbitmq_config), store)
    factory = RabbitMQS3UploadToOTCloudPayloadFactory(OT_CLOUD)
    delivered_payload = factory.create(_upload_event(1))
    returned_payload = factory.create(_upload_event(2))

    notifier.notify(delivered_payload)
    notifier.run_once()
    assert store.size() == 0, "The queue should have taken the first message"

    rabbitmq_channel.queue_delete(queue=QUEUE)
    notifier.notify(returned_payload)
    notifier.run_once()
    notifier.close()

    assert store.size() == 1
    oldest = store.oldest()
    assert oldest is not None
    assert oldest.read_text() == returned_payload
    assert not (tmp_path / "unreadable").exists()
