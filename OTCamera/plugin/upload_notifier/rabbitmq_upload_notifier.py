"""Non-blocking RabbitMQ publisher using a background daemon thread."""

import logging
import queue
import threading

import pika
import pika.exchange_type

from OTCamera.config import RabbitMqConfig
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)


class RabbitNotifier(Notifier):
    """Publish JSON messages to a RabbitMQ exchange via a background thread.

    notify() enqueues the payload and returns immediately; a daemon thread
    handles the actual TCP connection and publish.  If the broker is
    unreachable the error is logged and the message is dropped.
    """

    def __init__(self, config: RabbitMqConfig) -> None:
        self._config = config
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
        while True:
            payload = self._queue.get()
            try:
                self._publish(payload)
            except Exception:
                logger.exception(
                    "Failed to publish to RabbitMQ exchange='%s'",
                    self._config.exchange,
                )
            finally:
                self._queue.task_done()

    def _publish(self, payload: str) -> None:
        credentials = pika.PlainCredentials(self._config.user, self._config.password)
        parameters = pika.ConnectionParameters(
            host=self._config.host,
            port=self._config.port,
            virtual_host=self._config.vhost,
            credentials=credentials,
        )
        connection = pika.BlockingConnection(parameters)
        try:
            channel = connection.channel()
            channel.exchange_declare(
                exchange=self._config.exchange,
                exchange_type=pika.exchange_type.ExchangeType(
                    self._config.exchange_type
                ),
                durable=self._config.durable,
            )
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
        finally:
            connection.close()
