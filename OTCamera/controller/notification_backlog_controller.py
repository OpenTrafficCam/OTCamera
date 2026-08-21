"""Notification controller that drains the backlog of uploaded segments."""

import logging
from threading import Event, Thread

from OTCamera.controller.backlog import NotificationBacklog
from OTCamera.domain.notifier import Notifier, UploadPayloadFactory
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)

_INITIAL_WAIT_SECONDS = 5.0
_MAX_WAIT_SECONDS = 300.0
_IDLE_WAIT_SECONDS = 5.0
_CLOSE_TIMEOUT_SECONDS = 10.0


class NotificationBacklogController:
    """Announce every uploaded segment without losing a notification.

    A segment that reached the server waits in the notification backlog until
    the broker has confirmed the message about it. A background worker thread
    picks the oldest one, builds the message from the file itself, sends it,
    and deletes the file only once the broker has taken the message. A
    notification therefore survives a broker that is away, and a restart.

    What the message says is worked out from the file and the upload backend's
    settings, not remembered from the upload, so a segment left over from an
    earlier run can still be announced.

    Every failure is treated the same way: back off and retry the same
    segment, for as long as it takes. Nothing is skipped and nothing is set
    aside, so a segment the broker will never accept blocks the segments
    behind it and the backlog keeps growing.
    """

    def __init__(
        self,
        backlog: NotificationBacklog,
        upload: Upload,
        notifier: Notifier[str],
        payload_factory: UploadPayloadFactory[str],
    ) -> None:
        """Construct a new NotificationBacklogController instance.

        The worker thread is not started here; call `start` for that.

        Args:
            backlog (NotificationBacklog): The store of uploaded segments that
                are waiting to be announced.
            upload (Upload): The upload backend the segments went to, asked
                where each one is stored.
            notifier (Notifier[str]): The notifier that delivers the messages.
            payload_factory (UploadPayloadFactory[str]): Builds the message
                about an uploaded segment.
        """
        self._backlog = backlog
        self._upload = upload
        self._notifier = notifier
        self._payload_factory = payload_factory
        self._wait_seconds = _IDLE_WAIT_SECONDS
        self._head: str | None = None
        self._head_attempts = 0
        self._stop = Event()
        self._thread: Thread | None = None
        logger.debug("Notification backlog controller active")

    @property
    def backlog(self) -> NotificationBacklog:
        """Return the store of segments waiting to be announced."""
        return self._backlog

    @property
    def wait_seconds(self) -> float:
        """Return how long the worker waits before its next pass."""
        return self._wait_seconds

    @property
    def is_running(self) -> bool:
        """Return whether the worker thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the worker thread that drains the backlog."""
        if self.is_running:
            return
        self._stop.clear()
        self._thread = Thread(target=self._worker, daemon=True)
        self._thread.start()
        logger.info(
            "Notification worker started with %d segments to announce",
            self._backlog.size(),
        )

    def run_once(self) -> None:
        """Announce the waiting segments, oldest first, until none are left.

        Stops at the first failure and keeps the segment it failed on, along
        with the ones behind it, for the next pass. A pass also stops when the
        controller is closing.
        """
        segment = self._backlog.oldest()
        while segment is not None:
            # every segment costs one round-trip to the broker, so a long
            # backlog keeps this pass busy for a while. Leave the rest of it
            # to give a shutdown a chance to finish in time.
            if self._stop.is_set():
                return

            if segment.name != self._head:
                self._head = segment.name
                self._head_attempts = 0

            try:
                payload = self._payload_factory.create(self._upload.describe(segment))
                self._notifier.notify(payload)
            except Exception as exc:
                self._on_notification_failed(segment.name, exc)
                return

            self._backlog.remove(segment)
            self._backlog.count_notified()
            segment = self._backlog.oldest()

        self._head = None
        self._head_attempts = 0
        self._wait_seconds = _IDLE_WAIT_SECONDS

    def close(self) -> None:
        """Stop the worker thread and close the notifier.

        The notifier stays open when the worker does not stop in time, because
        the worker may still be using it.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=_CLOSE_TIMEOUT_SECONDS)
            if self._thread.is_alive():
                # the worker is still handing a message over. Closing the
                # notifier from here would cut that delivery in half. The
                # worker is a daemon, so it ends with the process and the
                # broker notices that.
                logger.warning(
                    "Notification worker did not stop within %.0f seconds,"
                    " leaving its notifier to the process shutdown",
                    _CLOSE_TIMEOUT_SECONDS,
                )
                return
        self._notifier.close()

    def _on_notification_failed(self, segment: str, exc: Exception) -> None:
        """Back off and keep the segment for the next pass.

        A segment's first failure sets the wait back to its starting value and
        each further failure doubles it, up to a cap, so a long outage is
        retried at a slow steady pace instead of at full speed.

        Args:
            segment (str): The name of the segment that will be retried
                unchanged.
            exc (Exception): The failure the notifier reported.
        """
        self._head_attempts += 1
        logger.warning(
            "Notification about %s failed (attempt %d): %s",
            segment,
            self._head_attempts,
            exc,
        )
        if self._head_attempts == 1:
            self._wait_seconds = _INITIAL_WAIT_SECONDS
        else:
            self._wait_seconds = min(self._wait_seconds * 2, _MAX_WAIT_SECONDS)

    def _worker(self) -> None:
        """Run one pass per wait interval until the controller is closed."""
        while not self._stop.wait(self._wait_seconds):
            try:
                self.run_once()
            except Exception:
                logger.exception("Notification pass failed unexpectedly")
