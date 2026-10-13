"""Non-blocking RabbitMQ publisher using a background daemon thread."""

import logging
import ssl
from threading import Event, Thread

from pika import (
    BasicProperties,
    ConnectionParameters,
    PlainCredentials,
    SSLOptions,
    exchange_type,
)
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from pika.exceptions import AMQPError, ConnectionWrongStateError

from OTCamera.config import RabbitMqConfig
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)

INITIAL_RECONNECT_DELAY_S = 1.0
MAX_RECONNECT_DELAY_S = 60.0
INITIAL_CONNECT_TIMEOUT_S = 10.0


def _connect(config: RabbitMqConfig) -> BlockingConnection:
    """Establish a blocking connection to the configured RabbitMQ broker.

    Args:
        config: Connection settings for the broker.

    Returns:
        An open blocking connection.

    Raises:
        AMQPConnectionError: If the broker cannot be reached or rejects the login.
    """
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
        # this is actually correct, mypy is confused
        ssl_options=ssl_options,  # type: ignore
    )
    return BlockingConnection(parameters)


def _setup_channel(
    connection: BlockingConnection,
    config: RabbitMqConfig,
) -> BlockingChannel:
    """Open a channel and declare the configured exchange and optional queue.

    Args:
        connection: The open connection to create the channel on.
        config: Exchange, queue and routing settings.

    Returns:
        The channel used for publishing.

    Raises:
        AMQPError: If the channel cannot be opened or a declaration fails.
    """
    channel = connection.channel()

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

    logger.info(
        "Setup RabbitMQ channel: exchange='%s', routing_key='%s', queue='%s'",
        config.exchange,
        config.routing_key,
        config.queue_name or "(none)",
    )

    return channel


def _close_quietly(connection: BlockingConnection | None) -> None:
    """Close the connection if it is open, ignoring errors.

    Args:
        connection: The connection to close, or None.
    """
    if connection is None or not connection.is_open:
        return
    try:
        connection.close()
    except (AMQPError, OSError) as exc:
        logger.debug("Ignoring error while closing connection: %r", exc)


class RabbitMqJsonPublisher(Thread):
    """A long-running publisher thread that publishes json-encoded payloads to RabbitMQ.

    The thread connects lazily and reconnects with exponential backoff whenever the
    connection is lost. Payloads published while disconnected are dropped.

    Adapted from
    https://github.com/pika/pika/blob/main/examples/long_running_publisher.py

    Attributes:
        shutdown_event: Event that stops the thread once it is set.
        connected: Event that is set while a connection is established.
        connection: The current connection, or None while disconnected.
        channel: The current channel, or None while disconnected.
    """

    def __init__(
        self,
        config: RabbitMqConfig,
        shutdown_event: Event,
        initial_reconnect_delay_s: float = INITIAL_RECONNECT_DELAY_S,
        max_reconnect_delay_s: float = MAX_RECONNECT_DELAY_S,
    ) -> None:
        """Initialize the publisher thread without connecting.

        Args:
            config: Connection, exchange and routing settings.
            shutdown_event: Event that stops the thread once it is set.
            initial_reconnect_delay_s: Delay before the first reconnect attempt.
            max_reconnect_delay_s: Upper bound for the exponential backoff delay.
        """
        super().__init__(name="rabbitmq-publisher", daemon=True)

        self.shutdown_event = shutdown_event
        self.connected = Event()

        self.connection: BlockingConnection | None = None
        self.channel: BlockingChannel | None = None

        self._config = config
        self._initial_reconnect_delay_s = initial_reconnect_delay_s
        self._max_reconnect_delay_s = max_reconnect_delay_s
        self._reconnect_delay_s = initial_reconnect_delay_s

    def run(self) -> None:
        """Keep the connection alive and dispatch publish callbacks until shutdown."""
        while not self.shutdown_event.is_set():
            if self.connection is None:
                self._connect_or_back_off()
            else:
                self._dispatch_events(self.connection)

        logger.debug("Received signal to stop publisher thread.")
        self._stop()

    def _connect_or_back_off(self) -> None:
        """Try to connect; on failure, wait and double the reconnect delay."""
        if self._try_connect():
            self._reconnect_delay_s = self._initial_reconnect_delay_s
            return

        # wait for the current reconnect delay, but wake up early on shutdown
        self.shutdown_event.wait(self._reconnect_delay_s)
        self._reconnect_delay_s = min(
            self._reconnect_delay_s * 2, self._max_reconnect_delay_s
        )

    def _dispatch_events(self, connection: BlockingConnection) -> None:
        """Dispatch pending publish callbacks and heartbeats for up to a second.

        Args:
            connection: The open connection to process events on.
        """
        try:
            connection.process_data_events(time_limit=1)
        except (AMQPError, OSError) as exc:
            logger.warning("Lost connection to RabbitMQ, reconnecting: %r", exc)
            self._discard_connection()
        except Exception:
            logger.exception("Unexpected error in RabbitMQ publisher, reconnecting.")
            self._discard_connection()

    def _try_connect(self) -> bool:
        """Connect to the broker and set up the channel.

        Returns:
            True if the connection was established, False otherwise.
        """
        connection = None
        try:
            connection = _connect(self._config)
            channel = _setup_channel(connection, self._config)
        except (AMQPError, OSError) as exc:
            logger.warning("Failed to connect to RabbitMQ: %r", exc)
            _close_quietly(connection)
            return False
        except Exception:
            logger.exception("Unexpected error while connecting to RabbitMQ.")
            _close_quietly(connection)
            return False

        self.connection = connection
        self.channel = channel
        logger.info("Connected to RabbitMQ at %s.", self._config.host)
        self.connected.set()
        return True

    def _discard_connection(self) -> None:
        """Close the current connection on a best-effort basis and forget it."""
        self.connected.clear()
        connection = self.connection
        self.connection = None
        self.channel = None
        _close_quietly(connection)

    def _publish(self, payload: str) -> None:
        """Publish a payload on the current channel.

        Must run on the publisher thread, so it is enqueued as a callback by
        `publish`.

        Args:
            payload: The JSON-encoded message body.
        """
        if self.channel is None:
            logger.warning("RabbitMQ channel is gone, dropping notification.")
            return
        properties = BasicProperties(
            content_type="application/json",
            delivery_mode=2 if self._config.durable else 1,
        )
        self.channel.basic_publish(
            exchange=self._config.exchange,
            routing_key=self._config.routing_key,
            body=payload,
            properties=properties,
        )
        logger.info(
            "Published '%s' to exchange='%s', routing_key='%s'",
            payload[:50] + "..." if len(payload) > 50 else payload,
            self._config.exchange,
            self._config.routing_key,
        )

    def publish(self, payload: str) -> None:
        """Publish a payload to the configured RabbitMQ exchange.

        This method is threadsafe and can be called from any thread. If there is
        currently no open connection, the payload is dropped with a warning.

        Args:
            payload: The JSON-encoded message body.

        Raises:
            ConnectionWrongStateError: If the connection closes between the
                connection check and enqueuing the callback.
        """
        connection = self.connection
        if connection is None or not connection.is_open:
            logger.warning("Not connected to RabbitMQ, dropping notification.")
            return
        connection.add_callback_threadsafe(lambda: self._publish(payload))

    def _stop(self) -> None:
        """Flush pending callbacks and close the connection."""
        if self.connection is not None:
            try:
                # Wait until all the data events have been processed
                self.connection.process_data_events(time_limit=1)
            except (AMQPError, OSError) as exc:
                logger.warning("Failed to flush pending RabbitMQ messages: %r", exc)
            self._discard_connection()
            logger.debug("Closed connection to RabbitMQ.")
        logger.debug("Stopped RabbitMQ publisher thread.")


class RabbitNotifier(Notifier):
    """Publish JSON messages to a RabbitMQ exchange via a publisher thread.

    Attributes:
        shutdown_event: Event that stops the publisher thread once it is set.
    """

    def __init__(
        self,
        config: RabbitMqConfig,
        connect_timeout_s: float = INITIAL_CONNECT_TIMEOUT_S,
    ) -> None:
        """Start the publisher thread and wait briefly for the first connection.

        Waiting keeps notifications sent right after startup from being dropped
        while the broker is reachable, without blocking startup indefinitely
        when it is not.

        Args:
            config: Connection, exchange and routing settings.
            connect_timeout_s: How long to wait for the first connection.
        """
        self.shutdown_event = Event()
        self._publisher = RabbitMqJsonPublisher(
            config, shutdown_event=self.shutdown_event
        )
        self._publisher.start()
        if not self._publisher.connected.wait(connect_timeout_s):
            logger.warning(
                "Not connected to RabbitMQ after %.0f s, retrying in background.",
                connect_timeout_s,
            )

    def notify(self, payload: str) -> None:
        """Publish a notification to RabbitMQ without raising on failure.

        Args:
            payload: The JSON-encoded message body.
        """
        try:
            self._publisher.publish(payload)
        except ConnectionWrongStateError as exc:
            logger.warning("Connection to RabbitMQ is not open: %s", exc)
        except Exception as exc:
            logger.warning("Failed to publish to RabbitMQ: %s", exc)

    def close(self) -> None:
        """Stop the publisher thread and close the connection."""
        self.shutdown_event.set()
        self._publisher.join(timeout=5)
        logger.info("Closed RabbitMQ notifier.")
