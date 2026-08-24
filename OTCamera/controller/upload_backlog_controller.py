"""Upload controller that drains the backlog of recorded segments."""

import logging
from pathlib import Path

from OTCamera.controller.backlog import NotificationBacklog, UploadBacklog
from OTCamera.controller.backlog_worker import BacklogWorker
from OTCamera.domain.events import EventBus, RecordingSplit
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadBacklogController:
    """Get finished recording segments to the server without losing any.

    The work is split across two threads. The camera thread hands a finished
    segment over by accepting it into the backlog. A background worker does
    everything else, one segment per pass: it picks the oldest segment, uploads
    it, takes it out of the backlog once the server has it, and reclaims space
    when the card fills up.

    Uploading and taking a segment out belong to the same controller because
    both take segments out of the backlog, so keeping them together means they
    never compete over the same segment.

    Where an uploaded segment goes depends on whether anyone has to be told
    about it. With a notification backlog, the segment moves there and waits
    for its notification; without one, it is deleted, because nothing would
    ever come to collect it.

    Every failure is treated the same way: the worker backs off and the next
    pass retries the same segment, for as long as it takes. Nothing is skipped
    and nothing is set aside. A segment the server will never accept therefore
    blocks the segments behind it, until reclaiming space deletes it and the
    backlog drains again.

    An upload backend is optional. Without one, segments are still taken out of
    the recording directory and space is still reclaimed; only the upload step
    is skipped, which does not count as a failure.
    """

    def __init__(
        self,
        event_bus: EventBus,
        upload: Upload | None,
        backlog: UploadBacklog,
        notification_backlog: NotificationBacklog | None,
    ):
        """Construct a new UploadBacklogController instance.

        Subscribes to the `RecordingSplit` event on the `EventBus`. The worker
        thread is not started here; call `start` for that.

        Args:
            event_bus (EventBus): The global event bus.
            upload (Upload | None): The upload backend to use, or None when none
                is configured. Without one the worker only reclaims space.
            backlog (UploadBacklog): The store of segments waiting to be uploaded.
            notification_backlog (NotificationBacklog | None): The store an
                uploaded segment waits in until it has been announced, or None
                when no notification is configured and uploaded segments are
                deleted right away.
        """
        self._upload = upload
        self._event_bus = event_bus
        self._backlog = backlog
        self._notification_backlog = notification_backlog
        self._worker = BacklogWorker("Upload", self.run_once)
        event_bus.subscribe(RecordingSplit, self._on_recording_split)
        logger.debug("Upload backlog controller active")

    @property
    def wait_seconds(self) -> float:
        """Return how long the worker waits before its next pass."""
        return self._worker.wait_seconds

    @property
    def is_running(self) -> bool:
        """Return whether the worker thread is alive."""
        return self._worker.is_running

    def start(self) -> None:
        """Start the worker thread that drains the backlog."""
        if self.is_running:
            return
        self._worker.start()
        logger.info(
            "Upload worker started with %d segments pending", self._backlog.size()
        )

    def run_once(self) -> None:
        """Perform exactly one pass over the backlog.

        Reclaims space first, so that a pass which cannot upload anything still
        keeps the card usable, then uploads the oldest segment.
        """
        self._backlog.reclaim_to_floor()

        if self._upload is None:
            self._worker.note_empty()
            return

        segment = self._backlog.oldest()
        if segment is None:
            self._worker.note_empty()
            return

        self._worker.note_working_on(segment.name)

        try:
            result = self._upload.upload(segment)
        except Exception as exc:
            self._worker.note_failure(exc)
            return

        self._hand_over(segment)
        self._event_bus.enqueue(result.to_upload_event())
        self._backlog.count_uploaded()
        self._worker.note_success()

    def close(self) -> None:
        """Stop the worker thread, giving the current upload time to finish."""
        self._worker.close()

    def _on_recording_split(self, event: RecordingSplit) -> None:
        """Accept the finished segment into the backlog.

        This runs on the camera thread and must never raise: nothing upstream
        retries the handover, and the recording has to go on undisturbed. A
        failure is therefore logged and costs that one segment its upload.

        Args:
            event (RecordingSplit): The event announcing the finished segment.
        """
        try:
            self._backlog.add(Path(event.filename))
        except Exception:
            logger.exception("Could not accept %s for upload", event.filename)

    def _hand_over(self, segment: Path) -> None:
        """Take a segment the server has out of the upload backlog.

        The segment moves on to wait for its notification, or is deleted when
        there is nothing waiting to announce it. A move that fails leaves the
        segment in the upload backlog, where the next pass uploads it again:
        the server takes the same file twice rather than the camera losing
        track of it.

        Args:
            segment (Path): The segment that reached the server.
        """
        if self._notification_backlog is None:
            self._backlog.remove(segment)
            return
        try:
            self._notification_backlog.add(segment)
        except OSError:
            logger.exception(
                "Could not hand %s over to be announced; it stays up for upload",
                segment.name,
            )
