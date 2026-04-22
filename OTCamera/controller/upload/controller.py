"""Upload controller that reacts to recording split events."""

import logging
import threading
from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as futures_wait
from datetime import datetime, timezone
from pathlib import Path

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
        if self._upload is None:
            return
        try:
            logger.info("Uploading %s", event.filename)
            result = self._upload.upload(event.filename)
            self._event_bus.publish(self._make_uploaded_event(result))
        except Exception as exc:
            logger.warning("Upload failed: %s", exc)


class ThreadedUploadController(UploadController):
    """Dispatch each upload to a separate thread."""

    def __init__(
        self, event_bus: EventBus, upload: Upload | None = None, max_workers: int = 1
    ):
        super().__init__(event_bus=event_bus, upload=upload)

        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._active_futures: set[Future] = set()
        self._futures_lock = threading.Lock()

    def _on_recording_split(self, event: RecordingSplit) -> None:
        if self._upload is None:
            return

        filename = event.filename

        def on_done(f: Future) -> None:
            with self._futures_lock:
                self._active_futures.discard(f)
            try:
                result = f.result()
                self._event_bus.enqueue(self._make_uploaded_event(result))
            except Exception as exc:
                logger.warning("Upload failed: %s", exc)

        f = self.thread_pool.submit(self._upload.upload, filename)
        with self._futures_lock:
            self._active_futures.add(f)
        logger.debug("Scheduled new upload task %d", id(f))
        f.add_done_callback(on_done)

    def close(
        self,
        wait: bool = True,
        cancel_pending: bool = True,
        grace_timeout: float | None = None,
    ) -> None:
        """Terminate the underlying ThreadPoolExecutor.

        Args:
            wait: Block until all running uploads finish (ignored when
                ``grace_timeout`` is set).
            cancel_pending: Cancel futures that have not started yet.
            grace_timeout: Seconds to wait for active uploads before returning
                without waiting further. Running uploads cannot be interrupted
                and will continue in the background. When ``None`` the
                behaviour of ``wait`` applies without a deadline.
        """
        if grace_timeout is not None:
            logger.info(
                "Requested graceful shutdown with %f second timeout", grace_timeout
            )
            logger.info(
                "Waiting for %d active uploads to finish", len(self._active_futures)
            )
            with self._futures_lock:
                active = set(self._active_futures)
            if active:
                _, still_running = futures_wait(active, timeout=grace_timeout)
                if still_running:
                    logger.warning(
                        "Grace period expired; %d upload(s) still running",
                        len(still_running),
                    )
            self.thread_pool.shutdown(wait=False, cancel_futures=cancel_pending)
        else:
            self.thread_pool.shutdown(wait=wait, cancel_futures=cancel_pending)
