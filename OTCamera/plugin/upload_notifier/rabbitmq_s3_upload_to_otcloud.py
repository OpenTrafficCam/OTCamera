import dataclasses
import json

from OTCamera.config import OTCloudSettings
from OTCamera.controller.upload.notification.controller import PayloadFactory
from OTCamera.domain.events import FileUploaded, S3FileUploaded
from OTCamera.plugin.upload_notifier.dtos import CameraIdDto, S3FileUploadedEvent


class RabbitMQS3UploadToOTCloudPayloadFactory(PayloadFactory):

    def __init__(self, ot_cloud_settings: OTCloudSettings):
        self.ot_cloud_settings = ot_cloud_settings

    def create(self, event: FileUploaded) -> str:
        # The EventBus subscription in UploadNotificationController already
        # filters to S3FileUploaded events, so this assert should never fire.
        # It is kept as a safety net against accidental misconfiguration at
        # the wiring site (e.g. wrong event_type passed to the controller).
        assert isinstance(event, S3FileUploaded)
        dto = S3FileUploadedEvent(
            s3_key=event.key,
            camera_id=CameraIdDto(
                camera_id=self.ot_cloud_settings.camera_id,
                project_id=self.ot_cloud_settings.project_id,
                site_id=self.ot_cloud_settings.site_id,
            ),
            timestamp=event.timestamp.isoformat(),
            original_filename=event.filename,
            new_filename=event.filename,
            bucket_name=event.bucket,
        )

        return json.dumps(dataclasses.asdict(dto))
