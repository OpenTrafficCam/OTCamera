"""Provides functionality for assessing the current network status.

Contains:
- NetworkProbe: Interface for classes that assess the network status.
- HttpNetworkProbe: Implementation of NetworkProbe that is based on http requests.
"""

import logging
from abc import ABC, abstractmethod
from typing import Sequence

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class NetworkProbe(ABC):
    """Interface for network probes."""

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

    def __init__(self, urls: Sequence[str], timeout: int | None):
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
        """Make a http request and asses the network status.

        Sends http requests to the urls defined in `HttpNetworkProbe.urls` in sequnce.

        If all requests result in a `RequestException`, the network status is
        considered OFFLINE.

        Returns:
            a boolean indicating whether our network connection can be considered
            online (True) or offline (False)
        """
        for url in self.urls:
            logger.debug("Sending network probe to %s", url)
            try:
                response = requests.head(
                    url, timeout=self.timeout, allow_redirects=False
                )
            except RequestException:
                logger.debug("Sending network probe to %s failed!", url)
                continue

            # Any HTTP response from a known domain confirms IP-level connectivity,
            # regardless of status code. Log >=400 status codes for visibility,
            # but stay online.
            if not response.ok:
                logger.warning(
                    "Network probe to %s returned status %d", url, response.status_code
                )
            return True
        return False
