"""Non-blocking RabbitMQ publisher using a background daemon thread."""

import logging
import ssl
import threading

import pika.exchange_type
from pika import BasicProperties, ConnectionParameters, PlainCredentials, SSLOptions
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection

from OTCamera.config import RabbitMqConfig
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)


def _connect(config: RabbitMqConfig) -> BlockingConnection:
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

    logger.info(
        "Setup RabbitMQ channel: exchange='%s', routing_key='%s', queue='%s'",
        config.exchange,
        config.routing_key,
        config.queue_name or "(none)",
    )

    return channel


# Adapted from https://github.com/pika/pika/blob/main/examples/long_running_publisher.py
class RabbitMqJsonPublisher(threading.Thread):

    def __init__(self, config: RabbitMqConfig) -> None:
        super().__init__(name="rabbitmq-publisher", daemon=True)

        self.is_running = True

        self.connection = _connect(config)
        self.channel = _setup_channel(self.connection, config)

        self._config = config

    def run(self) -> None:
        while self.is_running:
            self.connection.process_data_events(time_limit=1)

    def _publish(self, payload: str) -> None:
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
        self.connection.add_callback_threadsafe(lambda: self._publish(payload))

    def stop(self) -> None:
        self.is_running = False
        # Wait until all the data events have been processed
        self.connection.process_data_events(time_limit=1)
        if self.connection.is_open:
            self.connection.close()


class RabbitNotifier(Notifier):
    """Publish JSON messages to a RabbitMQ exchange via a publisher thread."""

    def __init__(self, config: RabbitMqConfig) -> None:
        self._publisher = RabbitMqJsonPublisher(config)

    def notify(self, payload: str) -> None:
        self._publisher.publish(payload)

    def close(self) -> None:
        """ "Close the underlying publisher."""
        self._publisher.stop()
