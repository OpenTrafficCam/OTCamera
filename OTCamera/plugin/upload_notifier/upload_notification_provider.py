"""Upload notification backend provider."""

import logging
from pathlib import Path

from OTCamera.config import Config
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)

# Notices are not videos; they wait outside the video tree.
_NOTICE_DIR = Path("~/notices")


class UploadNotificationProvider:
    """Create an upload notification backend from configuration."""

    @staticmethod
    def _create_rabbitmq(config: Config) -> Notifier:
        from OTCamera.controller.message_store import MessageStore
        from OTCamera.plugin.upload_notifier.rabbitmq_upload_notifier import (
            RabbitNotifier,
        )
        from OTCamera.plugin.upload_notifier.store_backed_notifier import (
            StoreBackedNotifier,
        )

        assert config.rabbitmq is not None  # guaranteed by config validation

        logger.debug("RabbitMQ upload notification backend enabled")
        notifier = StoreBackedNotifier(
            notifier=RabbitNotifier(config.rabbitmq),
            store=MessageStore(_NOTICE_DIR),
        )
        notifier.start()
        return notifier

    @staticmethod
    def provide(
        config: Config,
    ) -> Notifier | None:
        """Return the configured upload notification backend, or None if none is set.

        The returned notifier is ready to use; close it to release it.
        """
        if config.notification == "rabbitmq":
            return UploadNotificationProvider._create_rabbitmq(config)

        logger.info("No upload notification backend configured")
        return None
