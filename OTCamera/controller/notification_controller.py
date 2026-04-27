import logging
from abc import ABC, abstractmethod

from OTCamera.domain.events import Event, EventBus
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)


class PayloadFactory[EVENT: Event, PAYLOAD](ABC):
    """Transforms a domain event into a notification payload."""

    @abstractmethod
    def create(self, event: EVENT) -> PAYLOAD:
        """Build and return a payload from the given event."""
        raise NotImplementedError


class EventNotificationController[EVENT: Event, PAYLOAD]:
    """Subscribes to events and forwards them as payloads to a notifier."""

    def __init__(
        self,
        event_bus: EventBus,
        event_type: type[EVENT],
        notifier: Notifier[PAYLOAD],
        payload_factory: PayloadFactory[EVENT, PAYLOAD],
    ):
        event_bus.subscribe(event_type, self._on_event)
        logger.debug("Notification controller active for %s", event_type.__name__)

        self._notifier = notifier
        self._payload_factory = payload_factory

    def _on_event(self, event: EVENT) -> None:
        payload = self._payload_factory.create(event)

        try:
            self._notifier.notify(payload)
        except Exception as exc:
            logger.warning(
                "Failed to send notification for event %r: %s",
                event,
                exc,
            )

    def close(self) -> None:
        """Close the underlying notification backend."""
        self._notifier.close()
        logger.info("Notifcation controller closed.")
