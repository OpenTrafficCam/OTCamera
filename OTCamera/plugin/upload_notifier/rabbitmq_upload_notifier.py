"""RabbitMQ publisher that waits for the broker to confirm each message."""

import logging
import ssl

from pika import (
    BasicProperties,
    ConnectionParameters,
    PlainCredentials,
    SSLOptions,
    exchange_type,
)
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from pika.exceptions import AMQPConnectionError

from OTCamera.config import RabbitMqConfig
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)

# how long one socket operation may take, and how long opening a usable
# connection may take in total.
_SOCKET_TIMEOUT_SECONDS = 3.0
_STACK_TIMEOUT_SECONDS = 6.0


def _connect(config: RabbitMqConfig) -> BlockingConnection:
    """Establish a connection based on the user config."""
    credentials = PlainCredentials(config.user, config.password)

    ssl_options = None
    if config.ssl:
        # TODO: we only support the default SSL context for now
        # (using CAs trusted by the system).
        # Extend for custom CAs if required.
        context = ssl.create_default_context()
        ssl_options = SSLOptions(context=context, server_hostname=config.host)

    parameters = ConnectionParameters(
        host=config.host,
        port=config.port,
        virtual_host=config.vhost,
        credentials=credentials,
        # keep a failing attempt short enough to finish within the time a
        # shutdown waits for it. Giving up early costs nothing: the message
        # stays in the store and goes out on a later attempt.
        socket_timeout=_SOCKET_TIMEOUT_SECONDS,
        stack_timeout=_STACK_TIMEOUT_SECONDS,
        # this is actually correct, mypy is confused
        ssl_options=ssl_options,  # type: ignore
    )
    return BlockingConnection(parameters)


def _setup_channel(
    connection: BlockingConnection,
    config: RabbitMqConfig,
) -> BlockingChannel:
    """Setup a channel, declare the exchange and queue."""
    channel = connection.channel()

    channel.exchange_declare(
        exchange=config.exchange,
        exchange_type=exchange_type.ExchangeType(config.exchange_type),
        durable=config.durable,
    )

    channel.queue_declare(queue=config.queue_name, durable=config.durable)
    channel.queue_bind(
        queue=config.queue_name,
        exchange=config.exchange,
        routing_key=config.routing_key,
    )

    logger.info(
        "Setup RabbitMQ channel: exchange='%s', routing_key='%s', queue='%s'",
        config.exchange,
        config.routing_key,
        config.queue_name,
    )

    return channel


class RabbitNotifier(Notifier[str]):
    """Publish JSON messages to a RabbitMQ exchange.

    A call to `notify` returns only once the broker has confirmed the
    message and raises when it has not, so the caller knows whether the
    message may be discarded or must be kept for another attempt.

    The connection is opened on first use and kept for later messages.
    A connection found dead is replaced with a fresh one.

    Not threadsafe: all calls must come from the same thread.
    """

    def __init__(self, config: RabbitMqConfig) -> None:
        """Construct a new RabbitNotifier instance.

        No connection is opened here; that happens on the first `notify`.

        Args:
            config (RabbitMqConfig): The connection and exchange settings.
        """
        self._config = config
        self._connection: BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

    def notify(self, payload: str) -> None:
        """Publish the payload and wait for the broker to confirm it.

        Args:
            payload (str): The JSON-encoded message to publish.

        Raises:
            AMQPError: When the message could not be published or the
                broker did not confirm it.
        """
        had_connection = self._connection is not None
        try:
            self._publish(payload)
        except AMQPConnectionError:
            if not had_connection:
                # there was no connection to go stale, so opening one just
                # failed. A second attempt would wait for the same timeout
                # again before it fails the same way.
                raise
            # A held connection can die unnoticed while idle. Try once
            # more on a fresh one before reporting failure.
            self._reset()
            self._publish(payload)

    def close(self) -> None:
        """Close the connection to RabbitMQ, if one is open."""
        self._reset()
        logger.info("Closed RabbitMQ notifier.")

    def _publish(self, payload: str) -> None:
        """Publish one message and wait until the broker confirms it."""
        channel = self._ensure_channel()
        properties = BasicProperties(
            content_type="application/json",
            delivery_mode=2 if self._config.durable else 1,
        )
        channel.basic_publish(
            exchange=self._config.exchange,
            routing_key=self._config.routing_key,
            body=payload,
            properties=properties,
            # have the broker hand the message back when it would reach no
            # queue, so a message is never counted as delivered on its way
            # to nowhere.
            mandatory=True,
        )
        logger.info(
            "Published '%s' to exchange='%s', routing_key='%s'",
            payload[:50] + "..." if len(payload) > 50 else payload,
            self._config.exchange,
            self._config.routing_key,
        )

    def _ensure_channel(self) -> BlockingChannel:
        """Return a usable channel, connecting or reconnecting if needed."""
        if (
            self._connection is None
            or self._connection.is_closed
            or self._channel is None
            or self._channel.is_closed
        ):
            self._reset()
            self._connection = _connect(self._config)
            self._channel = _setup_channel(self._connection, self._config)
            self._channel.confirm_delivery()
        return self._channel

    def _reset(self) -> None:
        """Drop the current connection so the next publish starts fresh."""
        connection = self._connection
        self._connection = None
        self._channel = None
        if connection is not None and connection.is_open:
            try:
                connection.close()
            except Exception:
                logger.debug("Discarded a connection that failed to close cleanly.")
