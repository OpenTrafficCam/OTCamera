import dataclasses
import json

from OTCamera.config import OTCloudSettings
from OTCamera.controller.notification_controller import PayloadFactory
from OTCamera.domain.events import Event, S3FileUploaded
from OTCamera.plugin.upload_notifier.payloads import (
    CameraIdPayload,
    S3FileUploadedPayload,
)


class RabbitMQS3UploadToOTCloudPayloadFactory(PayloadFactory):
    """Builds a JSON-encoded S3FileUploadedPayload from an S3FileUploaded event."""

    def __init__(self, ot_cloud_settings: OTCloudSettings):
        self.ot_cloud_settings = ot_cloud_settings

    def create(self, event: Event) -> str:
        """Serialize an S3FileUploaded event to a JSON string for OTCloud."""
        # The EventBus subscription in EventNotificationController already
        # filters to S3FileUploaded events, so this assert should never fire.
        # It is kept as a safety net against accidental misconfiguration at
        # the wiring site (e.g. wrong event_type passed to the controller).
        assert isinstance(event, S3FileUploaded)

        filename = event.local_path.name

        payload = S3FileUploadedPayload(
            s3_key=event.key,
            camera_id=CameraIdPayload(
                camera_id=self.ot_cloud_settings.camera_id,
                project_id=self.ot_cloud_settings.project_id,
                site_id=self.ot_cloud_settings.site_id,
            ),
            timestamp=event.timestamp.isoformat(),
            # TODO: original_filename and new_filename are currently the same for
            # compatibility reasons (OTCloud expects both fields at the moment).
            # Rename or remove fields once they are no longer needed.
            original_filename=filename,
            new_filename=filename,
            bucket_name=event.bucket,
        )

        return json.dumps(dataclasses.asdict(payload))
