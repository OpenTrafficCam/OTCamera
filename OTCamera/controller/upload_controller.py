"""Upload controller that reacts to recording split events."""

import logging

from OTCamera.domain.events import EventBus, RecordingSplit
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadController:
    """Upload completed recording segments when they are split."""

    def __init__(self, event_bus: EventBus, upload: Upload | None = None) -> None:
        self._upload = upload
        if upload is not None:
            event_bus.subscribe(RecordingSplit, self._on_recording_split)
            logger.debug("Upload controller active")

    def _on_recording_split(self, event: RecordingSplit) -> None:
        """Upload the completed recording segment."""
        if self._upload is None:
            return
        try:
            logger.info("Uploading %s", event.filename)
            self._upload.upload(event.filename)
        except Exception as exc:
            logger.warning("Upload failed: %s", exc)
