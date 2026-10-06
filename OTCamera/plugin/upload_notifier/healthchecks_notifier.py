"""Non-blocking healthchecks.io pinger using a background worker thread."""

import logging
from queue import Queue
from threading import Thread

from requests import RequestException, Session

from OTCamera.config import HealthchecksConfig
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)

_CLOSE_TIMEOUT_SECONDS = 5.0


class _Stop:
    """Sentinel that tells the worker thread to exit."""


_STOP = _Stop()


class HealthchecksNotifier(Notifier[str]):
    """Send pings with a text body to a healthchecks.io ping URL.

    Pings are sent on a single background thread so that a slow or
    unreachable endpoint never blocks the thread dispatching events.
    Failed pings are logged and dropped: a missing ping is exactly what
    healthchecks.io is meant to report.
    """

    def __init__(self, config: HealthchecksConfig, session: Session | None = None):
        """Create a new HealthchecksNotifier and start its worker thread.

        Args:
            config (HealthchecksConfig): The healthchecks.io settings. Its
                `ping_url` must be set.
            session (Session | None): HTTP session used for pinging. A new one
                is created when omitted.
        """
        if config.ping_url is None:
            raise ValueError("HealthchecksNotifier requires a ping_url")
        self._ping_url = str(config.ping_url)
        self._timeout = config.timeout
        self._session = session or Session()
        self._queue: Queue[str | _Stop] = Queue()
        self._thread = Thread(target=self._worker, name="healthchecks", daemon=True)
        self._thread.start()

    def notify(self, payload: str) -> None:
        """Queue a ping carrying `payload` as its body and return immediately."""
        self._queue.put(payload)

    def close(self) -> None:
        """Send queued pings, stop the worker thread, and release the session."""
        self._queue.put(_STOP)
        self._thread.join(timeout=_CLOSE_TIMEOUT_SECONDS)
        self._session.close()
        logger.info("Closed healthchecks.io notifier.")

    def _worker(self) -> None:
        """Send queued pings until the stop sentinel arrives."""
        while not isinstance(payload := self._queue.get(), _Stop):
            try:
                self._ping(payload)
            except Exception:
                logger.exception("Unexpected error while pinging healthchecks.io")

    def _ping(self, payload: str) -> None:
        try:
            response = self._session.post(
                self._ping_url, data=payload.encode(), timeout=self._timeout
            )
            response.raise_for_status()
        except RequestException as exc:
            logger.warning("Failed to ping healthchecks.io: %s", exc)
            return
        logger.debug("Pinged healthchecks.io: %s", payload)
