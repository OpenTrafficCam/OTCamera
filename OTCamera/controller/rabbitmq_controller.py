"""Controller that publishes a RabbitMQ message after each successful upload."""

import logging
from pathlib import Path

from OTCamera.domain.events import EventBus, FileUploaded
from OTCamera.plugin.rabbitmq.rabbitmq_publisher import RabbitMqPublisher

logger = logging.getLogger(__name__)


class RabbitMqController:
    """Subscribe to FileUploaded events and notify RabbitMQ."""

    def __init__(self, event_bus: EventBus, publisher: RabbitMqPublisher) -> None:
        self._publisher = publisher
        event_bus.subscribe(FileUploaded, self._on_file_uploaded)

    def _on_file_uploaded(self, event: FileUploaded) -> None:
        message = {"filename": Path(event.filename).name}
        try:
            self._publisher.publish(message)
        except Exception as exc:
            logger.warning("Failed to publish RabbitMQ message: %s", exc)
