import dataclasses
import json

from OTCamera.config import OTCloudSettings
from OTCamera.domain.notifier import UploadPayloadFactory
from OTCamera.domain.upload import S3UploadResult, UploadResult
from OTCamera.plugin.upload_notifier.payloads import (
    CameraIdPayload,
    S3FileUploadedPayload,
)


class RabbitMQS3UploadToOTCloudPayloadFactory(UploadPayloadFactory[str]):
    """Builds a JSON-encoded S3FileUploadedPayload from an S3 upload."""

    def __init__(self, ot_cloud_settings: OTCloudSettings):
        self.ot_cloud_settings = ot_cloud_settings

    def create(self, upload: UploadResult) -> str:
        """Serialize an S3 upload to a JSON string for OTCloud.

        Args:
            upload (UploadResult): Where the file was stored. It has to be an
                S3 upload, because OTCloud is told a bucket and a key.
        """
        # the caller decides which upload backend it hands over, so a mismatch
        # is a wiring mistake rather than something that can happen at runtime.
        assert isinstance(upload, S3UploadResult)

        filename = upload.local_path.name

        payload = S3FileUploadedPayload(
            s3_key=upload.key,
            camera_id=CameraIdPayload(
                camera_id=self.ot_cloud_settings.camera_id,
                project_id=self.ot_cloud_settings.project_id,
                site_id=self.ot_cloud_settings.site_id,
            ),
            # TODO: report a time once it is settled which one OTCloud needs.
            # A message can go out long after its upload, so the moment it is
            # built is not the moment the file was uploaded.
            timestamp="",
            # TODO: original_filename and new_filename are currently the same for
            # compatibility reasons (OTCloud expects both fields at the moment).
            # Rename or remove fields once they are no longer needed.
            original_filename=filename,
            new_filename=filename,
            bucket_name=upload.bucket,
        )

        return json.dumps(dataclasses.asdict(payload))
