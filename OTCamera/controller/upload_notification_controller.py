"""Controller that publishes a RabbitMQ message after each successful S3 upload."""

import logging
from pathlib import Path

from OTCamera.config import OTCloudSettings
from OTCamera.domain.events import EventBus, S3FileUploaded
from OTCamera.domain.upload_notifier import UploadNotifier
from OTCamera.plugin.upload_notifier.dtos import CameraIdDto, S3FileUploadedEvent

logger = logging.getLogger(__name__)


class UploadNotificationController:
    """Subscribe to S3FileUploaded events and notify via a publisher."""

    def __init__(
        self,
        event_bus: EventBus,
        notifier: UploadNotifier,
        ot_cloud: OTCloudSettings,
    ) -> None:
        self._notifier = notifier
        self._ot_cloud = ot_cloud
        event_bus.subscribe(S3FileUploaded, self._on_s3_file_uploaded)

    def _on_s3_file_uploaded(self, event: S3FileUploaded) -> None:
        payload = S3FileUploadedEvent(
            s3_key=event.key,
            camera_id=CameraIdDto(
                camera_id=self._ot_cloud.camera_id,
                project_id=self._ot_cloud.project_id,
                site_id=self._ot_cloud.site_id,
            ),
            timestamp=event.timestamp.isoformat(),
            original_filename=event.original_filename,
            new_filename=Path(event.key).name,
            bucket_name=event.bucket,
        )
        try:
            self._notifier.notify(payload)
        except Exception as exc:
            logger.warning("Failed to notify about S3 upload %r: %s", event, exc)
