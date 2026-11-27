"""RabbitMQ notifier that publishes each message on its own confirmed connection."""

import logging
import ssl
from queue import Queue
from threading import Thread

from pika import (
    BasicProperties,
    ConnectionParameters,
    PlainCredentials,
    SSLOptions,
    exchange_type,
)
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from pika.exceptions import AMQPError

from OTCamera.config import RabbitMqConfig
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)

# Upper bound for reaching the broker, completing the TLS/AMQP handshake, and
# waiting while the broker blocks publishers (e.g. on a resource alarm).
CONNECT_TIMEOUT_S = 10
# Bounds the wait for a publisher confirm if the link dies mid-publish.
HEARTBEAT_S = 10
CLOSE_TIMEOUT_S = 5.0
LOGGED_PAYLOAD_PREVIEW_LENGTH = 50


class _Stop:
    """Sentinel that tells the worker thread to exit."""


_STOP = _Stop()


def _connection_parameters(config: RabbitMqConfig) -> ConnectionParameters:
    """Build connection parameters that fail within bounded time.

    Args:
        config (RabbitMqConfig): Connection settings for the broker.

    Returns:
        ConnectionParameters: Parameters for a single connection attempt.
    """
    ssl_options = None
    if config.ssl:
        # TODO: we only support the default SSL context for now
        # (using CAs trusted by the system).
        # Extend for custom CAs if required.
        context = ssl.create_default_context()
        ssl_options = SSLOptions(context=context, server_hostname=config.host)

    return ConnectionParameters(
        host=config.host,
        port=config.port,
        virtual_host=config.vhost,
        credentials=PlainCredentials(config.user, config.password),
        connection_attempts=1,
        socket_timeout=CONNECT_TIMEOUT_S,
        stack_timeout=CONNECT_TIMEOUT_S,
        blocked_connection_timeout=CONNECT_TIMEOUT_S,
        heartbeat=HEARTBEAT_S,
        # this is actually correct, mypy is confused
        ssl_options=ssl_options,  # type: ignore
    )


def _connect(config: RabbitMqConfig) -> BlockingConnection:
    """Open a blocking connection to the configured RabbitMQ broker.

    Args:
        config (RabbitMqConfig): Connection settings for the broker.

    Returns:
        BlockingConnection: An open blocking connection.

    Raises:
        AMQPConnectionError: If the broker cannot be reached or rejects the login.
    """
    return BlockingConnection(_connection_parameters(config))


def _setup_channel(
    connection: BlockingConnection,
    config: RabbitMqConfig,
) -> BlockingChannel:
    """Open a confirming channel and declare the exchange and optional queue.

    Args:
        connection (BlockingConnection): The open connection to create the
            channel on.
        config (RabbitMqConfig): Exchange, queue and routing settings.

    Returns:
        BlockingChannel: A channel in confirm mode, used for publishing.

    Raises:
        AMQPError: If the channel cannot be opened or a declaration fails.
    """
    channel = connection.channel()
    channel.confirm_delivery()

    channel.exchange_declare(
        exchange=config.exchange,
        exchange_type=exchange_type.ExchangeType(config.exchange_type),
        durable=config.durable,
    )

    if config.queue_name:
        channel.queue_declare(queue=config.queue_name, durable=config.durable)
        channel.queue_bind(
            queue=config.queue_name,
            exchange=config.exchange,
            routing_key=config.routing_key,
        )

    return channel


def _close_quietly(connection: BlockingConnection) -> None:
    """Close the connection if it is open, ignoring errors.

    Args:
        connection (BlockingConnection): The connection to close.
    """
    if not connection.is_open:
        return
    try:
        connection.close()
    except (AMQPError, OSError) as exc:
        logger.debug("Ignoring error while closing connection: %r", exc)


def _publish_once(config: RabbitMqConfig, payload: str) -> None:
    """Publish one payload on a new connection and wait for the broker's confirm.

    Args:
        config (RabbitMqConfig): Connection, exchange and routing settings.
        payload (str): The JSON-encoded message body.

    Raises:
        AMQPConnectionError: If the broker cannot be reached.
        UnroutableError: If no queue is bound for the routing key.
        NackError: If the broker refuses the message.
        AMQPError: If any other broker operation fails.
    """
    connection = _connect(config)
    try:
        channel = _setup_channel(connection, config)
        channel.basic_publish(
            exchange=config.exchange,
            routing_key=config.routing_key,
            body=payload,
            properties=BasicProperties(
                content_type="application/json",
                delivery_mode=2 if config.durable else 1,
            ),
            mandatory=True,
        )
    finally:
        _close_quietly(connection)


def _preview(payload: str) -> str:
    """Shorten a payload for informational log messages.

    Args:
        payload (str): The JSON-encoded message body.

    Returns:
        str: The payload, truncated with an ellipsis if it is long.
    """
    if len(payload) > LOGGED_PAYLOAD_PREVIEW_LENGTH:
        return payload[:LOGGED_PAYLOAD_PREVIEW_LENGTH] + "..."
    return payload


class RabbitNotifier(Notifier[str]):
    """Publish JSON messages to a RabbitMQ exchange from a background worker.

    Each message is published on its own short-lived connection, with publisher
    confirms and `mandatory=True`, so a message is only logged as published once
    the broker has routed it to a queue and acknowledged it. A failed message is
    logged with its full body and dropped; there is no retry. The next message
    simply connects again, so no reconnect or backoff logic is needed, and the
    broker never has to be reachable for the camera to start.

    This relies on the low message rate: one notification per uploaded video
    segment, i.e. at most about one per minute, plus short bursts while a
    backlog is uploaded. Re-evaluate the design if the rate increases
    considerably: every message pays a full TCP, TLS and AMQP handshake, which
    is cheap at that rate but not at many messages per second.

    `notify()` is called on the main recording loop, so it only enqueues the
    payload; a single worker thread does the network I/O, keeping messages in
    order and keeping an unreachable broker from stalling recording.
    """

    def __init__(self, config: RabbitMqConfig) -> None:
        """Start the worker thread without connecting to the broker.

        Args:
            config (RabbitMqConfig): Connection, exchange and routing settings.
        """
        self._config = config
        self._queue: Queue[str | _Stop] = Queue()
        self._thread = Thread(target=self._worker, name="rabbitmq", daemon=True)
        self._thread.start()

    def notify(self, payload: str) -> None:
        """Queue a message for publishing and return immediately.

        Args:
            payload (str): The JSON-encoded message body.
        """
        self._queue.put(payload)

    def close(self) -> None:
        """Publish queued messages, then stop the worker thread.

        Waits at most `CLOSE_TIMEOUT_S` for the worker; messages still queued
        after that are lost.
        """
        self._queue.put(_STOP)
        self._thread.join(timeout=CLOSE_TIMEOUT_S)
        if self._thread.is_alive():
            logger.warning(
                "RabbitMQ worker did not finish within %.0f s, "
                "queued notifications are lost.",
                CLOSE_TIMEOUT_S,
            )
        logger.info("Closed RabbitMQ notifier.")

    def _worker(self) -> None:
        """Publish queued messages until the stop sentinel arrives."""
        while not isinstance(payload := self._queue.get(), _Stop):
            self._publish(payload)

    def _publish(self, payload: str) -> None:
        """Publish one message, logging rather than raising any failure.

        Args:
            payload (str): The JSON-encoded message body.
        """
        try:
            _publish_once(self._config, payload)
        except Exception as exc:
            # the full body is logged so the notification can be re-sent by hand
            logger.warning("Dropping RabbitMQ notification (%r): %s", exc, payload)
            return
        logger.info(
            "Published '%s' to exchange='%s', routing_key='%s'",
            _preview(payload),
            self._config.exchange,
            self._config.routing_key,
        )
