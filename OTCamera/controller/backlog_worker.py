"""The background worker that keeps passing over a backlog."""

import logging
from collections.abc import Callable
from threading import Event, Thread

logger = logging.getLogger(__name__)

_INITIAL_WAIT_SECONDS = 0.0
_INITIAL_WAIT_SECONDS_FOR_RETRY = 5.0
_MAX_WAIT_SECONDS = 300.0
_IDLE_WAIT_SECONDS = 5.0
CLOSE_TIMEOUT_SECONDS = 10.0


class BacklogWorker:
    """Processes a backlog of files on a thread of its own.

    In a loop, make a processing pass over a backlog of files
    (oldest first) and (depending on success or failure),
    adjust the waiting time before the next pass.

    The thread is a daemon, so it ends with the process.

    Should be used by a BacklogController and a corresponding Backlog class:
    The backlog handles the "queue" of files to be processed, the worker (this class)
    provides common functionality on processing a backlog, while the
    controller defines the concrete action to be performed on each pass.
    """

    def __init__(self, name: str, run_once: Callable[[], None]) -> None:
        """Construct a new BacklogWorker instance.

        The thread is not started here; call `start` for that.

        Args:
            name (str): What the work is called in the log, e.g. `Upload`.
            run_once (Callable[[], None]): Makes one pass over the backlog.
        """
        self._name = name
        self._run_once = run_once
        self._wait_seconds = _IDLE_WAIT_SECONDS
        self._head: str | None = None
        self._head_attempts = 0
        self._stop = Event()
        self._thread: Thread | None = None

    @property
    def wait_seconds(self) -> float:
        """Return how long the worker waits before its next pass."""
        return self._wait_seconds

    @property
    def is_running(self) -> bool:
        """Return whether the thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_closing(self) -> bool:
        """Return whether the worker has been asked to stop.

        A pass that works through several items reads this between them, so a
        shutdown does not have to wait for the whole backlog.
        """
        return self._stop.is_set()

    def start(self) -> None:
        """Start the thread that makes the passes."""
        if self.is_running:
            return
        self._stop.clear()
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()

    def close(self) -> bool:
        """Ask the worker to stop and return whether it did.

        A pass in progress is given time to finish. False means the worker is
        still in one, and whatever it is using has to be left alone.
        """
        self._stop.set()
        if self._thread is None:
            return True
        self._thread.join(timeout=CLOSE_TIMEOUT_SECONDS)
        return not self._thread.is_alive()

    def note_working_on(self, item: str) -> None:
        """Track the item the passes are working on.

        Args:
            item (str): Name of the item. A name other than the one before it
                clears the attempts counted so far.
        """
        if item == self._head:
            return
        self._head = item
        self._head_attempts = 0

    def note_failure(self, exc: Exception) -> None:
        """Back off, so the item is retried at a slower pace.

        An item's first failure sets the wait to the retry interval and each
        further failure doubles it, up to a cap, so a long outage is retried at
        a slow steady pace instead of at full speed.

        Args:
            exc (Exception): The failure to report.
        """
        self._head_attempts += 1
        logger.warning(
            "%s of %s failed (attempt %d): %s",
            self._name,
            self._head,
            self._head_attempts,
            exc,
        )
        # Set the waiting seconds to _INITIAL_WAIT_SECONDS_FOR_RETRY.
        # This value should be different from 0 and will be doubled in the
        # following iterations, should they also be failing.
        if self._head_attempts == 1:
            self._wait_seconds = _INITIAL_WAIT_SECONDS_FOR_RETRY
        else:
            self._wait_seconds = min(self._wait_seconds * 2, _MAX_WAIT_SECONDS)

    def note_success(self) -> None:
        """Report that an item made it through, so the wait starts over."""
        self._head = None
        self._head_attempts = 0
        self._wait_seconds = _INITIAL_WAIT_SECONDS

    def note_empty(self) -> None:
        """Report that there is nothing left to work on."""
        self._head = None
        self._head_attempts = 0
        self._wait_seconds = _IDLE_WAIT_SECONDS

    def _loop(self) -> None:
        """Run one pass per wait interval until the worker is closed."""
        while not self._stop.wait(self._wait_seconds):
            try:
                self._run_once()
            except Exception:
                logger.exception("%s pass failed unexpectedly", self._name)
