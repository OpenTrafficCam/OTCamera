"""Synchronous RabbitMQ publisher using pika."""

import json
import logging

import pika
import pika.exchange_type

from OTCamera.config import RabbitMqConfig

logger = logging.getLogger(__name__)


class RabbitMqPublisher:
    """Publish JSON messages to a RabbitMQ exchange."""

    def __init__(self, config: RabbitMqConfig) -> None:
        self._config = config

    def publish(self, message: dict) -> None:
        """Open a connection, publish message as JSON, then close."""
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
            body = json.dumps(message).encode("utf-8")
            properties = pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2 if self._config.durable else 1,
            )
            channel.basic_publish(
                exchange=self._config.exchange,
                routing_key=self._config.routing_key,
                body=body,
                properties=properties,
            )
            logger.debug(
                "Published message to exchange='%s', routing_key='%s'",
                self._config.exchange,
                self._config.routing_key,
            )
        finally:
            connection.close()
