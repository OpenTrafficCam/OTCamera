import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock, Thread
from time import sleep, time
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
        """Send a network probe and assess the network status.
        
        Returns:
            a boolean indicating whether our network connection can be considered
            online (True) or offline (False)
        """
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
    # The updated NetworkStatus
    status: NetworkStatus
    # Unix timestamp of the last status change.
    last_changed_at: float


class NetworkStatusWriter:
    def __init__(self, out_file: Path):
        self.out_file = out_file

    def write(self, update: StatusUpdate) -> None:
        """Persist a network connection StatusUpdate.
        
        
        Args:
            update: The StatusUpdate instance to write to a file.
        """
        payload = {"status": update.status.name, "changed": update.last_changed_at}
        with open(self.out_file, "w") as f:
            json.dump(payload, f)

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
            update = None

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
                    update = StatusUpdate(status=self._current_status, last_changed_at=self._last_changed_at)

            if update is not None:
                for subscriber in self.subscribers:
                    subscriber(update)

            sleep(self.wait)

    def subscribe(self, subscriber: Callable[[StatusUpdate], None]) -> None:
        """Register a subscriber.
        
        Args:
            subscriber: A callable accepting a StatusUpdate that will be
                registered as a subscriber.
        """
        self.subscribers.add(subscriber)
