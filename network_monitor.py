import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock, Thread
from time import sleep, time, monotonic
from typing import Sequence

import requests
from requests.exceptions import RequestException


class NetworkStatus(Enum):
    """Indicates the current status of a network connection"""

    ONLINE = 1
    OFFLINE = 2
    UNKNOWN = 3


class NetworkProbe(ABC):
    @abstractmethod
    def is_online(self) -> bool:
        """Return whether the network connection can be considered to be 'online' (True) or not (False)."""
        ...


class HttpNetworkProbe(NetworkProbe):
    """Get the current network status based on a HTTP request to one or more URLs."""

    def __init__(self, urls: Sequence[str]):
        if len(urls) < 1:
            raise ValueError("HttpNetworkProbe requires at least one URL to check.")

        self.urls = urls

    def is_online(self) -> bool:
        for url in self.urls:
            logging.debug("Sending network probe to %s", url)
            try:
                requests.head(url, timeout=5, allow_redirects=False)
            except RequestException:
                logging.debug("Sending network probe to %s failed!", url)
                continue

            return True
        return False


@dataclass
class StatusUpdate:
    status: NetworkStatus
    last_changed_at: float


class NetworkStatusWriter:
    def __init__(self, out_file: Path):
        self.out_file = out_file

    def write(self, update: StatusUpdate) -> None:
        paylaod = {"status": update.status.name, "changed": time()}
        with open(self.out_file, "w") as f:
            json.dump(paylaod, f)

        logging.info("Wrote network status to %s" % str(self.out_file))


class NetworkMonitor(Thread):
    def __init__(
        self,
        probe: NetworkProbe,
        wait: int,
        success_threshold: int = 3,
        fail_threshold: int = 5,
    ):
        super().__init__(daemon=True, name="network-monitor")

        self.probe = probe
        self.wait = wait

        self._status_lock = Lock()
        self._current_status = NetworkStatus.UNKNOWN

        self._last_changed_at = time()
        self._last_changed_monotonic = monotonic()

        self.success_threshold = success_threshold
        self.fail_threshold = fail_threshold

        self.success_streak = 0
        self.fail_streak = 0

        self.subscribers = set()

    @property
    def status(self) -> NetworkStatus:
        with self._status_lock:
            return self._current_status

    def run(self) -> None:
        while True:
            status = self.probe.is_online()

            with self._status_lock:
                if status:
                    self.success_streak += 1
                    self.fail_streak = 0
                else:
                    self.fail_streak += 1
                    self.success_streak = 0

                changed = False
                if (
                    self._current_status != NetworkStatus.ONLINE
                    and self.success_streak >= self.success_threshold
                ):
                    self._current_status = NetworkStatus.ONLINE
                    changed = True
                elif (
                    self._current_status != NetworkStatus.OFFLINE
                    and self.fail_streak >= self.fail_threshold
                ):
                    self._current_status = NetworkStatus.OFFLINE
                    changed = True

                if changed:
                    self._last_changed_at = time()
                    logging.info(
                        "Updated network status to %s", self._current_status.name
                    )

                    for subscriber in self.subscribers:
                        subscriber(StatusUpdate(status=self._current_status, last_changed_at=self._last_changed_at))

            sleep(self.wait)

    def subscribe(self, subscriber: Callable[[StatusUpdate], None]) -> None:
        self.subscribers.add(subscriber)



@dataclass(eq=True, order=True, frozen=True)
class Escalation:
    """Seconds after which the escalation is triggered."""
    after: int
    callable: Callable


class EscalationWorker(Thread):
    def __init__(self, escalations: Sequence[Escalation]):

        super().__init__(daemon=True)

        self.escalations = sorted(escalations)
        self.history = set()

        self._lock = Lock()

        self._status = NetworkStatus.UNKNOWN
        self._last_changed_at = monotonic()

    def process_update(self, status_update: StatusUpdate) -> None:
        """Process an update of the network status."""

        logging.debug("EscalationWorker received status update.")

        with self._lock:
            # Clear the escalation history if we are back online!
            if self._status != NetworkStatus.ONLINE and status_update.status == NetworkStatus.ONLINE:
                self._history = set()

            self._status = status_update.status
            self._last_changed_at = monotonic()


    def run(self) -> None:

        while True:
            # check the current status.
            offline = False
            with self._lock:
                if self._status == NetworkStatus.OFFLINE:
                    offline = True
                    time_since = monotonic() - self._last_changed_at
                    logging.debug("We have been offline since %d seconds.", time_since)

            if offline:
                for i, escalation in enumerate(self.escalations):
                    if escalation not in self.history and time_since >= escalation.after:
                        logging.info("Executing escalation #%d", i)
                        escalation.callable()
                        self.history.add(escalation)

            sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    writer = NetworkStatusWriter(Path("/tmp/network.json"))

    escalations = [
        Escalation(after=15, callable=lambda: print("Boy, that escalated with a bit of a delay!")),
        Escalation(after=5, callable=lambda: print("Boy, that escalated quickly!"))
    ]
    escalation_worker = EscalationWorker(escalations)

    monitor = NetworkMonitor(
        probe=HttpNetworkProbe(urls=("https://platomo.de",)),
        wait=5,
        fail_threshold=2
    )
    monitor.subscribe(writer.write)
    monitor.subscribe(escalation_worker.process_update)

    escalation_worker.start()

    monitor.start()
    monitor.join()
