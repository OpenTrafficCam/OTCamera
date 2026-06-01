"""Provides code for continuous monitoring of a network connection.

This module provides:
- NetworkStatus: Enum that indicates the status of a network connection.
- StatusUpdate: Dataclass for holding a new status and timestamp of the change.
- NetworkMonitor: Continuously send network probes and inform subscribers about changes.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import Lock, Thread
from time import sleep, time

from OTCamera.netwatch.probe import NetworkProbe

logger = logging.getLogger(__name__)


class NetworkStatus(Enum):
    """Indicates the current status of a network connection."""

    ONLINE = 1
    OFFLINE = 2
    UNKNOWN = 3


@dataclass
class StatusUpdate:
    """An update about a changed network status.

    Carries the new status and timestamp of the status change.

    This is passed to subscriber functions of the NetworkMonitor.
    """

    # The updated NetworkStatus
    status: NetworkStatus
    # Unix timestamp of the last status change.
    last_changed_at: float


class NetworkMonitor(Thread):
    """Monitors the current network status."""

    def __init__(
        self,
        probe: NetworkProbe,
        wait: int,
        success_threshold: int = 3,
        fail_threshold: int = 5,
    ):
        """Create a new NetworkMonitor.

        Subclasses threading.Thread and registers itself as a daemon thread.
        Sets the inital state to UNKNOWN. Actual monitoring activity is started
        by calling `run()`

        Args:
            probe (NetworkProbe): The probe that checks the network connection.
            wait (int): The wait time between individual probes.
            success_threshold (int): The number of sucessful probes in sequence
                after which the status changes to ONLINE
            fail_threshold (int): Analogously, the number of sequential failed probes
                that result in an OFFLINE status.

        """
        super().__init__(daemon=True, name="network-monitor")

        self.probe = probe
        self.wait = wait

        self._status_lock = Lock()
        self._current_status = NetworkStatus.UNKNOWN

        self._last_changed_at = time()

        self.success_threshold = success_threshold
        self.fail_threshold = fail_threshold

        self._success_streak = 0
        self._fail_streak = 0

        self.subscribers: set[Callable[[StatusUpdate], None]] = set()

    @property
    def status(self) -> NetworkStatus:
        """Return the current network status."""
        with self._status_lock:
            return self._current_status

    def run(self) -> None:
        """Start the monitoring main loop."""
        while True:
            status = self.probe.is_online()
            update = None

            with self._status_lock:
                if status:
                    self._success_streak += 1
                    self._fail_streak = 0
                else:
                    self._fail_streak += 1
                    self._success_streak = 0

                changed = False
                if (
                    self._current_status != NetworkStatus.ONLINE
                    and self._success_streak >= self.success_threshold
                ):
                    self._current_status = NetworkStatus.ONLINE
                    changed = True
                elif (
                    self._current_status != NetworkStatus.OFFLINE
                    and self._fail_streak >= self.fail_threshold
                ):
                    self._current_status = NetworkStatus.OFFLINE
                    changed = True

                if changed:
                    self._last_changed_at = time()
                    logging.info(
                        "Updated network status to %s", self._current_status.name
                    )
                    update = StatusUpdate(
                        status=self._current_status,
                        last_changed_at=self._last_changed_at,
                    )

            if update is not None:
                for subscriber in list(self.subscribers):
                    try:
                        subscriber(update)
                    except Exception:
                        logging.exception(
                            "Subscriber %s raised an exception", subscriber
                        )

            sleep(self.wait)

    def subscribe(self, subscriber: Callable[[StatusUpdate], None]) -> None:
        """Register a function as a subscriber.

        **Note**: Subscriber functions will be executed on the
        same thread as NetworkMonitor and could potentially block
        the monitoring loop. Avoid long-running or potentially blocking
        operations.

        Args:
            subscriber: A callable accepting a StatusUpdate as its only argument.
        """
        self.subscribers.add(subscriber)
