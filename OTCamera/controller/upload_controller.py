"""Upload controller that reacts to recording split events."""

import abc
import logging
from concurrent.futures import ThreadPoolExecutor, Future

from OTCamera.domain.events import EventBus, RecordingSplit
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadController(abc.ABC):
    """Upload completed recording segments when they are split."""

    def __init__(self, event_bus: EventBus, upload: Upload | None = None) -> None:
        self._upload = upload
        if upload is not None:
            event_bus.subscribe(RecordingSplit, self._on_recording_split)
            logger.debug("Upload controller active")

    @abc.abstractmethod
    def _on_recording_split(self, event: RecordingSplit) -> None:
        ...


class BlockingUpoloadController(UploadController):

    def _on_recording_split(self, event: RecordingSplit) -> None:
        """Upload the completed recording segment."""
        if self._upload is None:
            return
        try:
            logger.info("Uploading %s", event.filename)
            self._upload.upload(event.filename)
        except Exception as exc:
            logger.warning("Upload failed: %s", exc)


class ThreadedUploadController(UploadController):
    """Dispatch each upload to a separate thread."""

    def __init__(self, event_bus: EventBus, upload: Upload | None = None, max_workers: int = 1):
        super().__init__(event_bus=event_bus, upload=upload)
        
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

    def _on_recording_split(self, event: RecordingSplit):
        if self._upload is None:
            return

        def log_finished(f: Future):
            logger.debug("Future %d finisehd", id(f))
        
        f = self.thread_pool.submit(self._upload.upload, event.filename)

        logger.debug("Scheduled new upload task %d", id(f))
        f.add_done_callback(log_finished)


    def close(self, wait: bool = True, cancel_pending: bool = True) -> None:
        """Terminate the underlying ThreadPoolExecutor."""
        self.thread_pool.shutdown(wait=wait, cancel_futures=cancel_pending)
