import logging
from abc import ABC, abstractmethod

from OTCamera.domain.events import EventBus, FileUploaded
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)


class PayloadFactory[T](ABC):
    @abstractmethod
    def create(self, event: FileUploaded) -> T:
        raise NotImplementedError


class UploadNotificationController[T]:
    def __init__(
        self,
        event_bus: EventBus,
        event_type: type[FileUploaded],
        notifier: Notifier[T],
        payload_factory: PayloadFactory[T],
    ):
        event_bus.subscribe(event_type, self._on_file_uploaded)
        logger.debug(
            "Upload notification controller active for %s", event_type.__name__
        )

        self._notifier = notifier
        self._payload_factory = payload_factory

    def _on_file_uploaded(self, event: FileUploaded) -> None:
        payload = self._payload_factory.create(event)

        try:
            self._notifier.notify(payload)
        except Exception as exc:
            logger.warning(
                "Failed to send upload notification for file %s: %s",
                event.filename,
                exc,
            )
