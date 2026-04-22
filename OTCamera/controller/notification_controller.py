import logging
from abc import ABC, abstractmethod

from OTCamera.domain.events import Event, EventBus
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)


class PayloadFactory[E: Event, T](ABC):
    """Transforms a domain event into a notification payload."""

    @abstractmethod
    def create(self, event: E) -> T:
        """Build and return a payload from the given event."""
        raise NotImplementedError


class EventNotificationController[E: Event, T]:
    """Subscribes to events and forwards them as payloads to a notifier."""

    def __init__(
        self,
        event_bus: EventBus,
        event_type: type[E],
        notifier: Notifier[T],
        payload_factory: PayloadFactory[E, T],
    ):
        event_bus.subscribe(event_type, self._on_event)
        logger.debug("Notification controller active for %s", event_type.__name__)

        self._notifier = notifier
        self._payload_factory = payload_factory

    def _on_event(self, event: E) -> None:
        payload = self._payload_factory.create(event)

        try:
            self._notifier.notify(payload)
        except Exception as exc:
            logger.warning(
                "Failed to send notification for event %r: %s",
                event,
                exc,
            )
