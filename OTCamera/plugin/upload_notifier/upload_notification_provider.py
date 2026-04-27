"""Upload notification backend provider."""

import logging

from OTCamera.config import Config
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)


class UploadNotificationProvider:
    """Create an upload notification backend from configuration."""

    @staticmethod
    def _create_rabbitmq(config: Config) -> Notifier:
        from OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier import (
            RabbitNotifier,
        )

        assert config.rabbitmq is not None  # guaranteed by config validation

        logger.debug("RabbitMQ upload notification backend enabled")
        return RabbitNotifier(config.rabbitmq)

    @staticmethod
    def provide(
        config: Config,
    ) -> Notifier | None:
        """Return the configured upload notification backend, or None if none is set."""
        if config.notification == "rabbitmq":
            return UploadNotificationProvider._create_rabbitmq(config)

        logger.info("No upload notification backend configured")
        return None
