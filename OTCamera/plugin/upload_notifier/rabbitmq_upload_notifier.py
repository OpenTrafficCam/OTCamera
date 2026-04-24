"""Non-blocking RabbitMQ publisher using a background daemon thread."""

import logging
import queue
import ssl
import threading
from typing import NamedTuple

import pika
import pika.exchange_type
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from pika.exceptions import (
    AuthenticationError,
    ChannelClosedByBroker,
    ConnectionClosedByBroker,
    IncompatibleProtocolError,
    ProbableAccessDeniedError,
    ProbableAuthenticationError,
)

from OTCamera.config import RabbitMqConfig
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)

# Broker reply codes where reconnecting with the same config will always fail.
_FATAL_CONNECTION_CODES = frozenset({403, 530})
_FATAL_CHANNEL_CODES = frozenset({403, 404, 406})


def _setup_channel(
    connection: BlockingConnection,
    config: RabbitMqConfig,
) -> BlockingChannel:
    channel = connection.channel()

    channel.exchange_declare(
        exchange=config.exchange,
        exchange_type=pika.exchange_type.ExchangeType(config.exchange_type),
        durable=config.durable,
    )

    if config.queue_name:
        channel.queue_declare(queue=config.queue_name, durable=config.durable)
        channel.queue_bind(
            queue=config.queue_name,
            exchange=config.exchange,
            routing_key=config.routing_key,
        )

    # Enable publisher confirms so basic_publish blocks until the broker acks.
    # Without this, a persistent connection has no synchronization barrier and
    # messages may not be processed by the broker before the caller returns.
    channel.confirm_delivery()

    logger.info(
        "Setup RabbitMQ channel: exchange='%s', routing_key='%s', queue='%s'",
        config.exchange,
        config.routing_key,
        config.queue_name or "(none)",
    )

    return channel


class _Session(NamedTuple):
    connection: BlockingConnection
    channel: BlockingChannel


class RabbitNotifier(Notifier):
    """Publish JSON messages to a RabbitMQ exchange via a background thread.

    notify() enqueues the payload and returns immediately; a daemon thread
    handles the actual TCP connection and publish.  The channel is set up once
    and reused across publishes; on failure the connection is closed and
    re-established before the next message is processed.

    On a fatal broker error the worker stops permanently.  Subsequent notify()
    calls are silently dropped so the rest of the application is unaffected.
    """

    def __init__(self, config: RabbitMqConfig) -> None:
        self._config = config
        self._queue: queue.Queue[str] = queue.Queue()
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="rabbitmq-publisher"
        )
        self._thread.start()

    def notify(self, payload: str) -> None:
        """Enqueue payload for background publishing; returns immediately.

        Silently drops the payload if the publisher has stopped due to a fatal
        broker error, so the caller is never blocked or raised against.
        """
        if self._stopped.is_set():
            logger.debug("RabbitMQ publisher stopped; dropping notification")
            return
        self._queue.put(payload)

    def flush(self) -> None:
        """Block until all enqueued messages have been published or dropped."""
        self._queue.join()

    def _worker(self) -> None:
        """Consume payloads from the queue, reusing the channel across publishes."""
        session: _Session | None = None
        while True:
            payload = self._queue.get()
            stop = False
            try:
                if session is None or session.channel.is_closed:
                    session = self._connect_and_setup()
                self._publish(session.channel, payload)
            except ConnectionClosedByBroker as e:
                if e.reply_code in _FATAL_CONNECTION_CODES:
                    logger.error(
                        "Broker rejected connection (code=%s reason=%s);"
                        " stopping publisher",
                        e.reply_code,
                        e.reply_text,
                    )
                    stop = True
                else:
                    logger.warning(
                        "Connection closed by broker (code=%s); will reconnect",
                        e.reply_code,
                    )
                session = self._close_session(session)
            except ChannelClosedByBroker as e:
                if e.reply_code in _FATAL_CHANNEL_CODES:
                    logger.error(
                        "Broker closed channel (code=%s reason=%s); stopping publisher",
                        e.reply_code,
                        e.reply_text,
                    )
                    stop = True
                else:
                    logger.warning(
                        "Broker closed channel (code=%s); will reconnect",
                        e.reply_code,
                    )
                session = self._close_session(session)
            except (
                AuthenticationError,
                ProbableAuthenticationError,
                ProbableAccessDeniedError,
                IncompatibleProtocolError,
            ) as e:
                logger.error(
                    "Fatal RabbitMQ configuration error (%s); stopping publisher",
                    type(e).__name__,
                )
                session = self._close_session(session)
                stop = True
            except Exception:
                logger.exception(
                    "Failed to publish to RabbitMQ exchange='%s'",
                    self._config.exchange,
                )
                session = self._close_session(session)
            finally:
                self._queue.task_done()
            if stop:
                self._stopped.set()
                self._drain_queue()
                break

    def _drain_queue(self) -> None:
        """Discard pending items so flush() never blocks after a fatal stop."""
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

    def _close_session(self, session: _Session | None) -> _Session | None:
        if session is not None:
            try:
                session.connection.close()
            except Exception:
                pass
        return None

    def _connect_and_setup(self) -> _Session:
        """Establish a new connection and set up the channel."""
        credentials = pika.PlainCredentials(self._config.user, self._config.password)

        ssl_options = None
        if self._config.ssl:
            # TODO: we only support the default SSL context for now
            # (using CAs trusted by the system).
            # Extend for custom CAs if required.
            context = ssl.create_default_context()
            ssl_options = pika.SSLOptions(
                context=context, server_hostname=self._config.host
            )

        parameters = pika.ConnectionParameters(
            host=self._config.host,
            port=self._config.port,
            virtual_host=self._config.vhost,
            credentials=credentials,
            # this is actually correct, mypy is confused
            ssl_options=ssl_options,  # type: ignore
        )
        connection = pika.BlockingConnection(parameters)
        channel = _setup_channel(connection, self._config)
        return _Session(connection, channel)

    def _publish(self, channel: BlockingChannel, payload: str) -> None:
        """Publish a single payload on an existing channel."""
        properties = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2 if self._config.durable else 1,
        )
        channel.basic_publish(
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
