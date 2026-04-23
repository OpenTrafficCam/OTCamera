"""Non-blocking RabbitMQ publisher using a background daemon thread."""

import logging
import queue
import threading
from typing import NamedTuple

import pika
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection

from OTCamera.config import RabbitMqConfig
from OTCamera.domain.notifier import Notifier
from OTCamera.plugin.upload_notifier.rabbitmq_channel_setup import SetupRabbitMqChannel

logger = logging.getLogger(__name__)


class _Session(NamedTuple):
    connection: BlockingConnection
    channel: BlockingChannel


class RabbitNotifier(Notifier):
    """Publish JSON messages to a RabbitMQ exchange via a background thread.

    notify() enqueues the payload and returns immediately; a daemon thread
    handles the actual TCP connection and publish.  The channel is set up once
    and reused across publishes; on failure the connection is closed and
    re-established before the next message is processed.
    """

    def __init__(self, config: RabbitMqConfig) -> None:
        self._config = config
        self._channel_setup = SetupRabbitMqChannel()
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="rabbitmq-publisher"
        )
        self._thread.start()

    def notify(self, payload: str) -> None:
        """Enqueue payload for background publishing; returns immediately."""
        self._queue.put(payload)

    def flush(self) -> None:
        """Block until all enqueued messages have been published or dropped."""
        self._queue.join()

    def _worker(self) -> None:
        """Consume payloads from the queue, reusing the channel across publishes."""
        session: _Session | None = None
        while True:
            payload = self._queue.get()
            try:
                if session is None or session.channel.is_closed:
                    session = self._connect_and_setup()
                self._publish(session.channel, payload)
            except Exception:
                logger.exception(
                    "Failed to publish to RabbitMQ exchange='%s'",
                    self._config.exchange,
                )
                if session is not None:
                    try:
                        session.connection.close()
                    except Exception:
                        pass
                    session = None
            finally:
                self._queue.task_done()

    def _connect_and_setup(self) -> _Session:
        """Establish a new connection and set up the channel."""
        credentials = pika.PlainCredentials(self._config.user, self._config.password)
        parameters = pika.ConnectionParameters(
            host=self._config.host,
            port=self._config.port,
            virtual_host=self._config.vhost,
            credentials=credentials,
        )
        connection = pika.BlockingConnection(parameters)
        channel = self._channel_setup.setup(connection, self._config)
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
