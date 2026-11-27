import logging
import time
from threading import Event
from typing import Callable, Generator
from unittest.mock import MagicMock

import pytest
from pika.exceptions import AMQPConnectionError, NackError, UnroutableError

from OTCamera.config import RabbitMqConfig
from OTCamera.plugin.upload_notifier import rabbitmq_upload_notifier
from OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier import (
    CONNECT_TIMEOUT_S,
    HEARTBEAT_S,
    RabbitNotifier,
)

WAIT_TIMEOUT_S = 2.0
POLL_INTERVAL_S = 0.01
PAYLOAD = '{"key": "value"}'
CONFIG = RabbitMqConfig(host="localhost", exchange="ex", routing_key="rk")


def _wait_for(condition: Callable[[], bool]) -> bool:
    """Poll a condition until it holds or the test timeout expires."""
    deadline = time.monotonic() + WAIT_TIMEOUT_S
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(POLL_INTERVAL_S)
    return condition()


def _fake_connection() -> MagicMock:
    """Create an open connection fake whose `close` marks it closed."""
    connection = MagicMock()
    connection.is_open = True

    def close() -> None:
        connection.is_open = False

    connection.close.side_effect = close
    return connection


@pytest.fixture
def channel(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    channel = MagicMock()
    monkeypatch.setattr(
        rabbitmq_upload_notifier,
        "_setup_channel",
        MagicMock(return_value=channel),
    )
    return channel


@pytest.fixture
def connections() -> list[MagicMock]:
    return []


@pytest.fixture
def connect(
    monkeypatch: pytest.MonkeyPatch, channel: MagicMock, connections: list[MagicMock]
) -> MagicMock:
    def open_connection(config: RabbitMqConfig) -> MagicMock:
        connection = _fake_connection()
        connections.append(connection)
        return connection

    mock = MagicMock(side_effect=open_connection)
    monkeypatch.setattr(rabbitmq_upload_notifier, "_connect", mock)
    return mock


@pytest.fixture
def notifier(connect: MagicMock) -> Generator[RabbitNotifier, None, None]:
    notifier = RabbitNotifier(CONFIG)
    yield notifier
    notifier.close()


def test_connection_parameters_fail_within_bounded_time() -> None:
    parameters = rabbitmq_upload_notifier._connection_parameters(
        RabbitMqConfig(host="localhost", ssl=False)
    )

    assert parameters.connection_attempts == 1
    assert parameters.socket_timeout == CONNECT_TIMEOUT_S
    assert parameters.stack_timeout == CONNECT_TIMEOUT_S
    assert parameters.blocked_connection_timeout == CONNECT_TIMEOUT_S
    assert parameters.heartbeat == HEARTBEAT_S


def test_setup_channel_enables_publisher_confirms() -> None:
    connection = MagicMock()

    rabbitmq_upload_notifier._setup_channel(connection, CONFIG)

    connection.channel.return_value.confirm_delivery.assert_called_once()


def test_construction_does_not_connect(
    connect: MagicMock, notifier: RabbitNotifier
) -> None:
    connect.assert_not_called()


def test_notify_publishes_mandatory_message_and_closes_connection(
    notifier: RabbitNotifier, channel: MagicMock, connections: list[MagicMock]
) -> None:
    notifier.notify(PAYLOAD)

    assert _wait_for(lambda: channel.basic_publish.called)
    kwargs = channel.basic_publish.call_args.kwargs
    assert kwargs["body"] == PAYLOAD
    assert kwargs["exchange"] == "ex"
    assert kwargs["routing_key"] == "rk"
    assert kwargs["mandatory"] is True
    assert _wait_for(lambda: connections[0].close.called)


def test_each_message_uses_its_own_connection(
    notifier: RabbitNotifier, channel: MagicMock, connections: list[MagicMock]
) -> None:
    notifier.notify("first")
    notifier.notify("second")

    assert _wait_for(lambda: channel.basic_publish.call_count == 2)
    assert len(connections) == 2
    assert _wait_for(lambda: all(c.close.called for c in connections))


@pytest.mark.parametrize(
    "error",
    [
        UnroutableError([]),
        NackError([]),
        ValueError("unexpected"),
    ],
)
def test_failed_publish_logs_payload_and_closes_connection(
    notifier: RabbitNotifier,
    channel: MagicMock,
    connections: list[MagicMock],
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    channel.basic_publish.side_effect = error

    with caplog.at_level(logging.WARNING):
        notifier.notify(PAYLOAD)
        assert _wait_for(lambda: "Dropping RabbitMQ notification" in caplog.text)

    assert PAYLOAD in caplog.text
    assert connections[0].close.called


def test_unreachable_broker_drops_message_and_next_one_reconnects(
    notifier: RabbitNotifier,
    connect: MagicMock,
    channel: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connect.side_effect = [AMQPConnectionError("unreachable"), _fake_connection()]

    with caplog.at_level(logging.WARNING):
        notifier.notify("first")
        notifier.notify("second")
        assert _wait_for(lambda: channel.basic_publish.called)

    assert "Dropping RabbitMQ notification" in caplog.text
    assert "first" in caplog.text
    assert channel.basic_publish.call_args.kwargs["body"] == "second"


def test_notify_does_not_block_while_broker_hangs(connect: MagicMock) -> None:
    release = Event()
    connect.side_effect = lambda config: release.wait() and _fake_connection()
    notifier = RabbitNotifier(CONFIG)
    try:
        started = time.monotonic()
        notifier.notify(PAYLOAD)
        notifier.notify(PAYLOAD)

        assert time.monotonic() - started < POLL_INTERVAL_S * 10
    finally:
        release.set()
        notifier.close()


def test_close_publishes_queued_messages(
    connect: MagicMock, channel: MagicMock
) -> None:
    notifier = RabbitNotifier(CONFIG)

    notifier.notify("first")
    notifier.notify("second")
    notifier.close()

    assert channel.basic_publish.call_count == 2


def test_close_gives_up_on_hanging_broker(
    monkeypatch: pytest.MonkeyPatch,
    connect: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(rabbitmq_upload_notifier, "CLOSE_TIMEOUT_S", 0.05)
    release = Event()
    connect.side_effect = lambda config: release.wait() and _fake_connection()
    notifier = RabbitNotifier(CONFIG)
    notifier.notify(PAYLOAD)
    try:
        with caplog.at_level(logging.WARNING):
            notifier.close()

        assert "did not finish" in caplog.text
    finally:
        release.set()
