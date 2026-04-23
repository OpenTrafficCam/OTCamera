"""Use case for setting up a RabbitMQ channel with exchange and optional queue."""

import logging

import pika
import pika.exchange_type
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection

from OTCamera.config import RabbitMqConfig

logger = logging.getLogger(__name__)


class SetupRabbitMqChannel:
    """Set up a RabbitMQ channel: declare exchange and optionally bind a named queue.

    This use case encapsulates the logic for:
    - Creating a channel from an existing connection
    - Declaring an exchange
    - Declaring and binding a queue to the exchange (when queue_name is configured)

    When no queue_name is configured the queue declaration and binding are skipped,
    which is appropriate for publish-only scenarios where the consumer is responsible
    for declaring its own queue.
    """

    def setup(
        self,
        connection: BlockingConnection,
        config: RabbitMqConfig,
    ) -> BlockingChannel:
        """Set up and return a channel ready for publishing.

        Args:
            connection: An established blocking RabbitMQ connection.
            config: RabbitMQ configuration including exchange and optional queue name.

        Returns:
            A configured channel with the exchange (and queue, if named) declared.
        """
        channel = connection.channel()

        channel.exchange_declare(
            exchange=config.exchange,
            exchange_type=pika.exchange_type.ExchangeType(config.exchange_type),
            durable=config.durable,
        )

        if config.queue_name:
            channel.queue_declare(
                queue=config.queue_name,
                durable=config.durable,
            )
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
