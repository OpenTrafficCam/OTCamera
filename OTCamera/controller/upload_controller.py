"""Upload controller that reacts to recording split events."""

import logging
from abc import ABC, abstractmethod
from queue import Queue, ShutDown
from threading import Thread

from OTCamera.domain.events import EventBus, FileUploaded, RecordingSplit
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadController(ABC):
    """Upload completed recording segments when they are split."""

    def __init__(self, event_bus: EventBus, upload: Upload) -> None:
        """Initialize the a new `UploadController` with the given `Upload` implementation.
        
        Subscribes to the `RecordingSplit` event on the `EventBus`.

        Args:
            event_bus (EventBus): The event bus to subscribe to.
            upload (Upload): The upload backend implementation.
        """
        self._upload = upload
        self._event_bus = event_bus
        event_bus.subscribe(RecordingSplit, self._on_recording_split)
        logger.debug("Upload controller active")

    @abstractmethod
    def _on_recording_split(self, event: RecordingSplit) -> None:
        """Handle a completed recording segment.

        Implementations must upload the file at `event.filename` and publish a
        `FileUploaded` event on success. On failure the error should be logged
        without propagating.

        Args:
            event (RecordingSplit): The event triggering the upload. Contains the
                path to the file to be uploaded.
        """
        ...


class BlockingUploadController(UploadController):
    """An `UploadController` that blocks the thread it is running in.
    
    Only for testing purposes, should not be used in production.
    """


    def _on_recording_split(self, event: RecordingSplit) -> None:
        """Upload the completed recording segment."""
        try:
            logger.info("Uploading %s", event.filename)
            self._upload.upload(event.filename)
            self._event_bus.publish(FileUploaded(filename=event.filename))
        except Exception as exc:
            logger.warning("Upload failed: %s", exc)


class ThreadedUploadController(UploadController):
    """Upload files sequentially via a single background worker thread."""

    def __init__(self, event_bus: EventBus, upload: Upload):
        """Construct a new ThreadedUploadController instance.

        Args:
            event_bus (EventBus): The global event bus.
            upload (Upload): The upload backend to use.
        """
        super().__init__(event_bus=event_bus, upload=upload)
        self._queue: Queue[str] = Queue()
        self._thread = Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self) -> None:
        while True:
            try:
                filename = self._queue.get()
            except ShutDown:
                break
            try:
                logger.info("Uploading %s", filename)
                self._upload.upload(filename)
                self._event_bus.enqueue(FileUploaded(filename=filename))
            except Exception as exc:
                logger.warning("Upload failed: %s", exc)
            finally:
                self._queue.task_done()

    def _on_recording_split(self, event: RecordingSplit) -> None:
        try:
            self._queue.put(event.filename)
        except ShutDown:
            logger.warning(
                "Upload controller is shut down, ignoring %s", event.filename
            )

    def close(self, wait: bool = False) -> None:
        """Stop accepting new uploads and shut down the worker.

        Args:
          wait (bool): If True, blocks until all queued uploads finish.
        """
        # Shutdown prevents any further .put() actions.
        # Draining the queue with .get() is still allowed (immediate=False).
        self._queue.shutdown(immediate=False)

        # optional wait for all uploads to complete before returning.
        if wait:
            self._queue.join()
