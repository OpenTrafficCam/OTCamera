import logging
import time
from threading import Event
from typing import Callable, Generator
from unittest.mock import MagicMock

import pytest
from pika.exceptions import (
    AMQPChannelError,
    AMQPConnectionError,
    AMQPHeartbeatTimeout,
)

from OTCamera.config import RabbitMqConfig
from OTCamera.plugin.upload_notifier import rabbitmq_upload_notifier
from OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier import (
    RabbitMqJsonPublisher,
    RabbitNotifier,
)

TEST_RECONNECT_DELAY_S = 0.01
WAIT_TIMEOUT_S = 2.0
POLL_INTERVAL_S = 0.01


def _wait_for(condition: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + WAIT_TIMEOUT_S
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(POLL_INTERVAL_S)
    return condition()


def _fake_connection() -> MagicMock:
    connection = MagicMock()
    connection.is_open = True
    connection.process_data_events.side_effect = lambda time_limit: time.sleep(
        POLL_INTERVAL_S
    )
    return connection


@pytest.fixture
def setup_channel(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(rabbitmq_upload_notifier, "_setup_channel", mock)
    return mock


@pytest.fixture
def connect(monkeypatch: pytest.MonkeyPatch, setup_channel: MagicMock) -> MagicMock:
    mock = MagicMock(side_effect=lambda config: _fake_connection())
    monkeypatch.setattr(rabbitmq_upload_notifier, "_connect", mock)
    return mock


@pytest.fixture
def shutdown_event() -> Event:
    return Event()


@pytest.fixture
def publisher(shutdown_event: Event) -> Generator[RabbitMqJsonPublisher, None, None]:
    publisher = RabbitMqJsonPublisher(
        RabbitMqConfig(host="localhost"),
        shutdown_event=shutdown_event,
        initial_reconnect_delay_s=TEST_RECONNECT_DELAY_S,
        max_reconnect_delay_s=TEST_RECONNECT_DELAY_S,
    )
    yield publisher
    shutdown_event.set()
    if publisher.is_alive():
        publisher.join(timeout=WAIT_TIMEOUT_S)


def test_construction_does_not_connect(
    connect: MagicMock, publisher: RabbitMqJsonPublisher
) -> None:
    connect.assert_not_called()


def test_retries_until_broker_is_reachable(
    connect: MagicMock, publisher: RabbitMqJsonPublisher
) -> None:
    connect.side_effect = [
        AMQPConnectionError("unreachable"),
        AMQPConnectionError("unreachable"),
        _fake_connection(),
    ]

    publisher.start()

    assert publisher.connected.wait(WAIT_TIMEOUT_S)
    assert connect.call_count == 3


def test_reconnects_after_heartbeat_timeout(
    connect: MagicMock, publisher: RabbitMqJsonPublisher
) -> None:
    lost_connection = _fake_connection()
    lost_connection.process_data_events.side_effect = AMQPHeartbeatTimeout(
        "missed heartbeats"
    )
    new_connection = _fake_connection()
    connect.side_effect = [lost_connection, new_connection]

    publisher.start()

    assert _wait_for(lambda: publisher.connection is new_connection)
    assert publisher.is_alive()
    assert publisher.connected.is_set()


def test_publish_while_disconnected_drops_payload(
    publisher: RabbitMqJsonPublisher, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        publisher.publish('{"key": "value"}')

    assert "dropping notification" in caplog.text


def test_publish_while_connected_enqueues_callback(
    connect: MagicMock, publisher: RabbitMqJsonPublisher
) -> None:
    publisher.start()
    assert publisher.connected.wait(WAIT_TIMEOUT_S)
    connection = publisher.connection
    assert isinstance(connection, MagicMock)

    publisher.publish('{"key": "value"}')

    connection.add_callback_threadsafe.assert_called_once()


def test_shutdown_during_backoff_stops_promptly(
    connect: MagicMock, shutdown_event: Event
) -> None:
    connect.side_effect = AMQPConnectionError("unreachable")
    publisher = RabbitMqJsonPublisher(
        RabbitMqConfig(host="localhost"),
        shutdown_event=shutdown_event,
        initial_reconnect_delay_s=60,
        max_reconnect_delay_s=60,
    )
    publisher.start()
    try:
        assert _wait_for(lambda: connect.call_count >= 1)

        shutdown_event.set()
        publisher.join(timeout=WAIT_TIMEOUT_S)

        assert not publisher.is_alive()
    finally:
        shutdown_event.set()


def test_shutdown_closes_open_connection(
    connect: MagicMock, publisher: RabbitMqJsonPublisher, shutdown_event: Event
) -> None:
    publisher.start()
    assert publisher.connected.wait(WAIT_TIMEOUT_S)
    connection = publisher.connection
    assert isinstance(connection, MagicMock)

    shutdown_event.set()
    publisher.join(timeout=WAIT_TIMEOUT_S)

    assert not publisher.is_alive()
    connection.close.assert_called_once()
    assert publisher.connection is None


def test_unexpected_error_while_connecting_does_not_kill_thread(
    connect: MagicMock, publisher: RabbitMqJsonPublisher
) -> None:
    connect.side_effect = [ValueError("unexpected"), _fake_connection()]

    publisher.start()

    assert publisher.connected.wait(WAIT_TIMEOUT_S)
    assert publisher.is_alive()


def test_unexpected_error_while_dispatching_reconnects(
    connect: MagicMock, publisher: RabbitMqJsonPublisher
) -> None:
    broken_connection = _fake_connection()
    broken_connection.process_data_events.side_effect = TypeError("unexpected")
    new_connection = _fake_connection()
    connect.side_effect = [broken_connection, new_connection]

    publisher.start()

    assert _wait_for(lambda: publisher.connection is new_connection)
    assert publisher.is_alive()


def test_connection_is_not_exposed_before_channel_is_ready(
    connect: MagicMock,
    setup_channel: MagicMock,
    publisher: RabbitMqJsonPublisher,
) -> None:
    connection = _fake_connection()
    connect.side_effect = [connection]
    connection_during_setup: list[object] = []

    def fail_setup(connection: MagicMock, config: RabbitMqConfig) -> None:
        connection_during_setup.append(publisher.connection)
        raise AMQPChannelError("precondition failed")

    setup_channel.side_effect = fail_setup

    publisher.start()

    assert _wait_for(lambda: connection.close.called)
    assert connection_during_setup[0] is None
    assert publisher.connection is None
    assert not publisher.connected.is_set()


def test_notifier_waits_for_first_connection(connect: MagicMock) -> None:
    notifier = RabbitNotifier(
        RabbitMqConfig(host="localhost"), connect_timeout_s=WAIT_TIMEOUT_S
    )
    try:
        connection = notifier._publisher.connection
        assert isinstance(connection, MagicMock)

        notifier.notify('{"key": "value"}')

        connection.add_callback_threadsafe.assert_called_once()
    finally:
        notifier.close()


def test_notifier_starts_when_broker_is_unreachable(
    connect: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    connect.side_effect = AMQPConnectionError("unreachable")

    with caplog.at_level(logging.WARNING):
        notifier = RabbitNotifier(
            RabbitMqConfig(host="localhost"), connect_timeout_s=TEST_RECONNECT_DELAY_S
        )
    notifier.close()

    assert "retrying in background" in caplog.text
