"""Upload controller that reacts to recording split events."""

import logging
from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor

from OTCamera.domain.events import EventBus, FileUploaded, RecordingSplit
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadController(ABC):
    """Upload completed recording segments when they are split."""

    def __init__(self, event_bus: EventBus, upload: Upload | None = None) -> None:
        self._upload = upload
        self._event_bus = event_bus
        if upload is not None:
            event_bus.subscribe(RecordingSplit, self._on_recording_split)
            logger.debug("Upload controller active")

    @abstractmethod
    def _on_recording_split(self, event: RecordingSplit) -> None:
        """Handle a completed recording segment.

        Implementations must upload the file at ``event.filename`` and publish a
        ``FileUploaded`` event on success. On failure the error should be logged
        without propagating.
        """
        ...


class BlockingUploadController(UploadController):

    def _on_recording_split(self, event: RecordingSplit) -> None:
        """Upload the completed recording segment."""
        if self._upload is None:
            return
        try:
            logger.info("Uploading %s", event.filename)
            self._upload.upload(event.filename)
            self._event_bus.publish(FileUploaded(filename=event.filename))
        except Exception as exc:
            logger.warning("Upload failed: %s", exc)


class ThreadedUploadController(UploadController):
    """Dispatch each upload to a separate thread."""

    def __init__(
        self, event_bus: EventBus, upload: Upload | None = None, max_workers: int = 1
    ):
        super().__init__(event_bus=event_bus, upload=upload)

        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

    def _on_recording_split(self, event: RecordingSplit) -> None:
        if self._upload is None:
            return

        filename = event.filename

        def on_done(f: Future) -> None:
            try:
                f.result()
                self._event_bus.publish(FileUploaded(filename=filename))
            except Exception as exc:
                logger.warning("Upload failed: %s", exc)

        f = self.thread_pool.submit(self._upload.upload, filename)
        logger.debug("Scheduled new upload task %d", id(f))
        f.add_done_callback(on_done)

    def close(self, wait: bool = True, cancel_pending: bool = True) -> None:
        """Terminate the underlying ThreadPoolExecutor."""
        self.thread_pool.shutdown(wait=wait, cancel_futures=cancel_pending)
