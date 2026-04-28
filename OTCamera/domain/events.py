"""Hybrid event bus and event types for OTCamera."""

import logging
import queue
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar, cast

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """Base class for all events."""

    pass


@dataclass(frozen=True)
class RecordingStarted(Event):
    """A new recording has started."""

    filename: str


@dataclass(frozen=True)
class RecordingStopped(Event):
    """The current recording has stopped."""


@dataclass(frozen=True)
class RecordingSplit(Event):
    """A recording interval has completed."""

    filename: str


@dataclass(frozen=True)
class IntervalFinished(Event):
    """Reserved for future calendar-based scheduling."""


@dataclass(frozen=True)
class BatteryLow(Event):
    """The battery dropped below the shutdown threshold."""


@dataclass(frozen=True)
class ExternalPowerConnected(Event):
    """External power has been connected."""


@dataclass(frozen=True)
class ExternalPowerDisconnected(Event):
    """External power has been disconnected."""


@dataclass(frozen=True)
class ButtonPressed(Event):
    """A button or switch was pressed."""

    name: str


@dataclass(frozen=True)
class ButtonHeld(Event):
    """A button was held."""

    name: str


@dataclass(frozen=True)
class ButtonReleased(Event):
    """A button or switch was released."""

    name: str


@dataclass(frozen=True)
class PreviewCaptured(Event):
    """A preview image was captured."""

    path: str


@dataclass(frozen=True)
class WifiOn(Event):
    """Wi-Fi access point was enabled."""


@dataclass(frozen=True)
class WifiOff(Event):
    """Wi-Fi access point was disabled."""


@dataclass(frozen=True)
class ShutdownRequested(Event):
    """Shutdown was requested by a subsystem."""

    source: str


@dataclass(frozen=True)
class FileUploaded(Event):
    """A file was successfully uploaded to remote storage."""

    local_path: Path
    timestamp: datetime


@dataclass(frozen=True)
class S3FileUploaded(FileUploaded):
    """A file was successfully uploaded to S3."""

    # the bucket to which the file was uploaded.
    bucket: str

    # the key as which the file was stored in S3.
    key: str


EVENT = TypeVar("EVENT", bound="Event")


class EventBus:
    """Hybrid in-process event bus with synchronous and queued dispatch."""

    def __init__(self) -> None:
        self._subscribers: dict[type[Event], list[Callable[[Event], None]]] = {}
        self._queue: "queue.Queue[Any]" = queue.Queue()

    def subscribe(
        self, event_type: type[EVENT], callback: Callable[[EVENT], None]
    ) -> None:
        """Register a callback for an event type."""
        self._subscribers.setdefault(event_type, []).append(
            # Callbacks are stored as Callable[[Event], None] because the dict
            # is keyed by event type and _dispatch only calls a callback with
            # the matching event subtype. The cast is safe: contravariance
            # prevents direct assignment but the runtime contract is upheld.
            cast(Callable[[Event], None], callback)
        )

    def unsubscribe(
        self,
        event_type: type[EVENT],
        callback: Callable[[EVENT], None],
    ) -> None:
        """Remove a callback for an event type if it is registered."""
        callbacks = self._subscribers.get(event_type)
        if callbacks is None:
            return
        try:
            callbacks.remove(
                cast(Callable[[Event], None], callback)
            )  # mirrors subscribe cast
        except ValueError:
            return
        if not callbacks:
            del self._subscribers[event_type]

    def publish(self, event: Event) -> None:
        """Dispatch an event synchronously to all subscribers."""
        self._dispatch(event)

    def enqueue(self, event: Event) -> None:
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

    def _dispatch(self, event: Event) -> None:
        """Dispatch an event and log callback failures without propagating."""
        for event_type, callbacks in self._subscribers.items():
            if not isinstance(event, event_type):
                continue
            for callback in callbacks:
                try:
                    callback(event)
                except Exception:
                    logger.exception(
                        "Event callback %s failed for %s",
                        callback,
                        type(event).__name__,
                    )
