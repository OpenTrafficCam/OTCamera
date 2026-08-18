"""Notifier that keeps messages in a store until they are delivered."""

import logging
from threading import Event, Thread

from OTCamera.controller.message_store import MessageStore
from OTCamera.domain.notifier import Notifier

logger = logging.getLogger(__name__)

_INITIAL_WAIT_SECONDS = 5.0
_MAX_WAIT_SECONDS = 300.0
_IDLE_WAIT_SECONDS = 5.0
_CLOSE_TIMEOUT_SECONDS = 10.0


class StoreBackedNotifier(Notifier[str]):
    """Get notifications to the wrapped notifier without losing any.

    A call to `notify` only files the payload in the store and returns; it
    never fails because of the receiving side. A worker thread delivers the
    stored messages oldest-first and removes each one only after the wrapped
    notifier has accepted it, so a message survives until it is delivered.

    Every delivery failure is treated the same way: pause, back off, and
    retry the same message, for as long as it takes. A message that cannot
    be read is the exception: it is set aside instead of retried.
    """

    def __init__(self, notifier: Notifier[str], store: MessageStore) -> None:
        """Construct a new StoreBackedNotifier instance.

        The worker thread is not started here; call `start` for that.

        Args:
            notifier (Notifier[str]): The notifier that delivers the messages.
            store (MessageStore): The store holding the undelivered messages.
        """
        self._notifier = notifier
        self._store = store
        self._wait_seconds = _IDLE_WAIT_SECONDS
        self._head: str | None = None
        self._head_attempts = 0
        self._stop = Event()
        self._wake = Event()
        self._thread: Thread | None = None

    @property
    def wait_seconds(self) -> float:
        """Return how long the worker waits before its next pass."""
        return self._wait_seconds

    @property
    def is_running(self) -> bool:
        """Return whether the worker thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the worker thread that delivers the stored messages."""
        if self.is_running:
            return
        self._stop.clear()
        self._thread = Thread(target=self._worker, daemon=True)
        self._thread.start()
        logger.info(
            "Notification worker started with %d messages pending", self._store.size()
        )

    def notify(self, payload: str) -> None:
        """File the payload in the store and wake the worker to deliver it.

        Args:
            payload (str): The message to deliver.
        """
        self._store.add(message=payload)
        self._wake.set()

    def run_once(self) -> None:
        """Deliver stored messages oldest-first until the store is empty.

        Stops at the first delivery failure and keeps the failed message
        and all newer ones for the next pass. A message that cannot be read
        is set aside and the pass continues with the next one. A pass also
        stops when the notifier is closing.
        """
        oldest = self._store.oldest()
        while oldest is not None:
            # every message costs one round-trip to the receiving side, so
            # a full store keeps this pass busy for a long time. Leave the
            # rest of it to give a shutdown a chance to finish in time.
            if self._stop.is_set():
                return

            if oldest.name != self._head:
                self._head = oldest.name
                self._head_attempts = 0

            try:
                payload = oldest.read_text()
            except (OSError, UnicodeDecodeError):
                # a message that cannot be read will not become readable
                # later, and keeping it would hold back every message
                # behind it. Set it aside so the store keeps draining.
                logger.exception("Setting unreadable message %s aside", oldest.name)
                self._store.quarantine(oldest.name)
                oldest = self._store.oldest()
                continue

            try:
                self._notifier.notify(payload)
            except Exception as exc:
                self._on_delivery_failed(oldest.name, exc)
                return

            self._store.remove(oldest.name)
            oldest = self._store.oldest()

        self._head = None
        self._head_attempts = 0
        self._wait_seconds = _IDLE_WAIT_SECONDS

    def close(self) -> None:
        """Stop the worker thread and close the wrapped notifier.

        The wrapped notifier stays open when the worker does not stop in
        time, because the worker may still be using it.
        """
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=_CLOSE_TIMEOUT_SECONDS)
            if self._thread.is_alive():
                # the worker is still handing a message over. Closing the
                # notifier from here would cut that delivery in half. The
                # worker is a daemon, so it ends with the process and the
                # receiving side notices that.
                logger.warning(
                    "Notification worker did not stop within %.0f seconds,"
                    " leaving its notifier to the process shutdown",
                    _CLOSE_TIMEOUT_SECONDS,
                )
                return
        self._notifier.close()

    def _on_delivery_failed(self, message: str, exc: Exception) -> None:
        """Back off and keep the message for the next pass.

        The wait starts at five seconds for a message's first failure and
        doubles with each further one, so during a long outage the worker
        retries every five minutes instead of every five seconds.

        Args:
            message (str): The name of the message that will be retried
                unchanged.
            exc (Exception): The failure the notifier reported.
        """
        self._head_attempts += 1
        logger.warning(
            "Delivery of %s failed (attempt %d): %s",
            message,
            self._head_attempts,
            exc,
        )
        if self._head_attempts == 1:
            self._wait_seconds = _INITIAL_WAIT_SECONDS
        else:
            self._wait_seconds = min(self._wait_seconds * 2, _MAX_WAIT_SECONDS)

    def _worker(self) -> None:
        """Run one pass per wait interval, or sooner when a message arrives.

        A new message only shortens the wait between two successful passes,
        not the wait a failed delivery asked for.
        """
        while not self._stop.is_set():
            if self._head_attempts > 0:
                # the oldest message is stuck. A newer message behind it
                # does not change that, so it must not cut the wait short:
                # the retry would only repeat the same failure sooner.
                self._stop.wait(self._wait_seconds)
            else:
                self._wake.wait(self._wait_seconds)
            self._wake.clear()
            if self._stop.is_set():
                break
            try:
                self.run_once()
            except Exception:
                logger.exception("Notification pass failed unexpectedly")
