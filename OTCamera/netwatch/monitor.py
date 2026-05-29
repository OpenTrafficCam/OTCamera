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

logger = logging.getLogger(__name__)


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

    def __init__(self, urls: Sequence[str], timeout: int | None = None):
        """Create a new HttpNetworkProbe.

        Args:
            urls (Sequence[str]): The urls that will be probed in sequence to determine
                the state of the network connection. Cannot be empty.
            timeout (int | None): Optional timeout for outgoing http requests.
                If the timeout is exceeded, the probe counts as failed.
        """
        if len(urls) < 1:
            raise ValueError("HttpNetworkProbe requires at least one URL to check.")

        self.urls = urls
        self.timeout = timeout

    def is_online(self) -> bool:
        for url in self.urls:
            logger.debug("Sending network probe to %s", url)
            try:
                response = requests.head(
                    url, timeout=self.timeout, allow_redirects=False
                )
            except RequestException:
                logging.debug("Sending network probe to %s failed!", url)
                continue

            # Any HTTP response from a known domain confirms IP-level connectivity,
            # regardless of status code. Log non-2xx for visibility but stay online.
            if not response.ok:
                logging.warning(
                    "Network probe to %s returned status %d", url, response.status_code
                )
            return True
        return False


@dataclass
class StatusUpdate:
    """An update about a changed network status.

    This is passed to subscriber functions of the NetworkManager.
    """

    # The updated NetworkStatus
    status: NetworkStatus
    # Unix timestamp of the last status change.
    last_changed_at: float


class NetworkStatusWriter:
    """Writes the network status to a file.

    The `write()` method can be used as a subscriber to
    NetworkMonitor status updates.
    """

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

        logger.debug("Wrote network status to %s", self.out_file)


class NetworkMonitor(Thread):
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
