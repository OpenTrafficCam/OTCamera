from typing import Generator
from unittest.mock import patch

import pytest
from pika.exceptions import ChannelWrongStateError, StreamLostError

from OTCamera.config import RabbitMqConfig
from OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier import (
    RabbitNotifier,
    _connect,
)

_MODULE = "OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier"

# how long a shutdown waits for the worker that publishes.
_SHUTDOWN_TIMEOUT_SECONDS = 10.0


class FakeChannel:
    def __init__(self, publish_failures: list[Exception | None] | None = None) -> None:
        """Fail the n-th publish with the n-th entry, None to let it through."""
        self.published: list[str] = []
        self.confirms_enabled = False
        self.is_closed = False
        self._publish_failures = publish_failures or []

    def confirm_delivery(self) -> None:
        self.confirms_enabled = True

    def basic_publish(
        self,
        exchange: str,
        routing_key: str,
        body: str,
        properties: object,
        mandatory: bool = False,
    ) -> None:
        if self._publish_failures:
            failure = self._publish_failures.pop(0)
            if failure is not None:
                raise failure
        self.published.append(body)
        self.last_mandatory = mandatory
        self.last_properties = properties


class FakeConnection:
    def __init__(self, channel: FakeChannel) -> None:
        self.channel = channel
        self.is_open = True

    @property
    def is_closed(self) -> bool:
        return not self.is_open

    def close(self) -> None:
        self.is_open = False


@pytest.fixture
def config() -> RabbitMqConfig:
    return RabbitMqConfig(
        host="localhost",
        exchange="uploads",
        routing_key="file_uploaded",
        queue_name="notifications",
        ssl=False,
        durable=False,
    )


@pytest.fixture
def connections() -> list[FakeConnection]:
    return []


@pytest.fixture
def notifier(
    config: RabbitMqConfig, connections: list[FakeConnection]
) -> Generator[RabbitNotifier, None, None]:
    with (
        patch(f"{_MODULE}._connect", side_effect=connections),
        patch(f"{_MODULE}._setup_channel", side_effect=lambda conn, cfg: conn.channel),
    ):
        yield RabbitNotifier(config)


class TestConnecting:
    def test_gives_up_on_a_connection_within_the_shutdown_timeout(
        self, config: RabbitMqConfig
    ) -> None:
        with patch(f"{_MODULE}.BlockingConnection") as connection:
            _connect(config)

        parameters = connection.call_args.args[0]
        assert parameters.socket_timeout < parameters.stack_timeout
        assert parameters.stack_timeout < _SHUTDOWN_TIMEOUT_SECONDS


class TestPublishing:
    def test_publishes_confirmed_and_mandatory(
        self, notifier: RabbitNotifier, connections: list[FakeConnection]
    ) -> None:
        channel = FakeChannel()
        connections.append(FakeConnection(channel))

        notifier.notify("hello")

        assert channel.published == ["hello"]
        assert channel.confirms_enabled
        assert channel.last_mandatory

    def test_reuses_the_connection_for_later_messages(
        self, notifier: RabbitNotifier, connections: list[FakeConnection]
    ) -> None:
        channel = FakeChannel()
        connections.append(FakeConnection(channel))

        notifier.notify("first")
        notifier.notify("second")

        assert channel.published == ["first", "second"]


class TestReconnecting:
    def test_retries_once_on_a_fresh_connection_when_the_held_one_died(
        self, notifier: RabbitNotifier, connections: list[FakeConnection]
    ) -> None:
        dead = FakeChannel(publish_failures=[None, StreamLostError("gone")])
        fresh = FakeChannel()
        connections.extend([FakeConnection(dead), FakeConnection(fresh)])
        notifier.notify("first")

        notifier.notify("second")

        assert dead.published == ["first"]
        assert fresh.published == ["second"]

    def test_raises_when_the_retry_fails_too(
        self, notifier: RabbitNotifier, connections: list[FakeConnection]
    ) -> None:
        connections.extend(
            [
                FakeConnection(
                    FakeChannel(publish_failures=[None, StreamLostError("gone")])
                ),
                FakeConnection(
                    FakeChannel(publish_failures=[StreamLostError("still gone")])
                ),
            ]
        )
        notifier.notify("first")

        with pytest.raises(StreamLostError):
            notifier.notify("second")

    def test_does_not_retry_when_there_was_no_connection_to_replace(
        self, config: RabbitMqConfig
    ) -> None:
        spare = FakeConnection(FakeChannel())
        with (
            patch(
                f"{_MODULE}._connect",
                side_effect=[StreamLostError("no route"), spare],
            ) as connect,
            patch(
                f"{_MODULE}._setup_channel", side_effect=lambda conn, cfg: conn.channel
            ),
        ):
            with pytest.raises(StreamLostError):
                RabbitNotifier(config).notify("hello")

        assert connect.call_count == 1
        assert spare.channel.published == []

    def test_replaces_a_connection_found_closed(
        self, notifier: RabbitNotifier, connections: list[FakeConnection]
    ) -> None:
        first = FakeConnection(FakeChannel())
        second = FakeConnection(FakeChannel())
        connections.extend([first, second])

        notifier.notify("first")
        first.is_open = False
        notifier.notify("second")

        assert second.channel.published == ["second"]

    def test_does_not_retry_channel_level_errors(
        self, notifier: RabbitNotifier, connections: list[FakeConnection]
    ) -> None:
        failing = FakeChannel(publish_failures=[ChannelWrongStateError("refused")])
        connections.append(FakeConnection(failing))

        with pytest.raises(ChannelWrongStateError):
            notifier.notify("hello")

        assert failing.published == []


class TestClose:
    def test_closes_an_open_connection(
        self, notifier: RabbitNotifier, connections: list[FakeConnection]
    ) -> None:
        connection = FakeConnection(FakeChannel())
        connections.append(connection)
        notifier.notify("hello")

        notifier.close()

        assert connection.is_closed

    def test_close_without_a_connection_does_not_raise(
        self, notifier: RabbitNotifier
    ) -> None:
        notifier.close()
