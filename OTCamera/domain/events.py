"""Hybrid event bus and event types for OTCamera."""

import logging
import queue
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordingStarted:
    """A new recording has started."""

    filename: str


@dataclass(frozen=True)
class RecordingStopped:
    """The current recording has stopped."""


@dataclass(frozen=True)
class RecordingSplit:
    """A recording interval has completed."""

    filename: str


@dataclass(frozen=True)
class IntervalFinished:
    """Reserved for future calendar-based scheduling."""


@dataclass(frozen=True)
class BatteryLow:
    """The battery dropped below the shutdown threshold."""


@dataclass(frozen=True)
class ExternalPowerConnected:
    """External power has been connected."""


@dataclass(frozen=True)
class ExternalPowerDisconnected:
    """External power has been disconnected."""


@dataclass(frozen=True)
class ButtonPressed:
    """A button or switch was pressed."""

    name: str


@dataclass(frozen=True)
class ButtonHeld:
    """A button was held."""

    name: str


@dataclass(frozen=True)
class ButtonReleased:
    """A button or switch was released."""

    name: str


@dataclass(frozen=True)
class PreviewCaptured:
    """A preview image was captured."""

    path: str


@dataclass(frozen=True)
class WifiOn:
    """Wi-Fi access point was enabled."""


@dataclass(frozen=True)
class WifiOff:
    """Wi-Fi access point was disabled."""


@dataclass(frozen=True)
class ShutdownRequested:
    """Shutdown was requested by a subsystem."""

    source: str


class EventBus:
    """Hybrid in-process event bus with synchronous and queued dispatch."""

    def __init__(self) -> None:
        self._subscribers: dict[type[Any], list[Callable[[Any], None]]] = {}
        self._queue: "queue.Queue[Any]" = queue.Queue()

    def subscribe(self, event_type: type[Any], callback: Callable[[Any], None]) -> None:
        """Register a callback for an event type."""
        self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(
        self,
        event_type: type[Any],
        callback: Callable[[Any], None],
    ) -> None:
        """Remove a callback for an event type if it is registered."""
        callbacks = self._subscribers.get(event_type)
        if callbacks is None:
            return
        try:
            callbacks.remove(callback)
        except ValueError:
            return
        if not callbacks:
            del self._subscribers[event_type]

    def publish(self, event: Any) -> None:
        """Dispatch an event synchronously to all subscribers."""
        self._dispatch(event)

    def enqueue(self, event: Any) -> None:
        """Enqueue an event for later dispatch on the calling thread."""
        self._queue.put(event)

    def process_pending(self) -> None:
        """Dispatch all currently queued events."""
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                return
            self._dispatch(event)

    def clear(self) -> None:
        """Remove all subscribers and drain queued events."""
        self._subscribers.clear()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def _dispatch(self, event: Any) -> None:
        """Dispatch an event and log callback failures without propagating."""
        for callback in list(self._subscribers.get(type(event), [])):
            try:
                callback(event)
            except Exception:
                logger.exception(
                    "Event callback %s failed for %s",
                    callback,
                    type(event).__name__,
                )
