"""Upload controller that reacts to recording split events."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, ShutDown
from threading import Thread

from OTCamera.domain.events import (
    EventBus,
    FileUploaded,
    RecordingSplit,
    S3FileUploaded,
)
from OTCamera.domain.upload import S3UploadResult, Upload, UploadResult

logger = logging.getLogger(__name__)


class UploadController(ABC):
    """Upload completed recording segments when they are split."""

    def __init__(self, event_bus: EventBus, upload: Upload) -> None:
        self._upload = upload
        self._event_bus = event_bus
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

    def _make_uploaded_event(self, result: UploadResult) -> FileUploaded:
        """Build the appropriate FileUploaded domain event from an upload result."""
        ts = datetime.now(tz=timezone.utc)

        if isinstance(result, S3UploadResult):
            return S3FileUploaded(
                filename=result.local_path,
                timestamp=ts,
                bucket=result.bucket,
                key=result.key,
                original_filename=Path(result.local_path).name,
            )
        return FileUploaded(filename=result.local_path, timestamp=ts)


class BlockingUploadController(UploadController):

    def _on_recording_split(self, event: RecordingSplit) -> None:
        """Upload the completed recording segment."""
        try:
            logger.info("Uploading %s", event.filename)
            result = self._upload.upload(event.filename)
            self._event_bus.publish(self._make_uploaded_event(result))
        except Exception as exc:
            logger.warning("Upload failed: %s", exc)


class ThreadedUploadController(UploadController):
    """Upload files sequentially via a single background worker thread."""

    def __init__(self, event_bus: EventBus, upload: Upload):
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
                result = self._upload.upload(filename)
                self._event_bus.enqueue(self._make_uploaded_event(result))
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

        If ``wait`` is True, blocks until all queued uploads finish.
        """
        # Shutdown prevents any further .put() actions.
        # Draining the queue with .get() is still allowed (immediate=False).
        self._queue.shutdown(immediate=False)

        # optional wait for all uploads to complete before returning.
        if wait:
            self._queue.join()
