import json
from pathlib import Path

from OTCamera.config import OTCloudSettings
from OTCamera.domain.upload import S3UploadResult
from OTCamera.plugin.upload_notifier.payload_factories import (
    RabbitMQS3UploadToOTCloudPayloadFactory,
)

OT_CLOUD = OTCloudSettings(camera_id=2, project_id=0, site_id=1)


def _upload(name: str) -> S3UploadResult:
    return S3UploadResult(
        local_path=Path("/videos/uploaded") / name,
        bucket="videos",
        key=f"site/cam/{name}",
    )


def _payload(upload: S3UploadResult) -> dict:
    return json.loads(RabbitMQS3UploadToOTCloudPayloadFactory(OT_CLOUD).create(upload))


def test_carries_key_bucket_filename_and_camera() -> None:
    name = "otcamera_FR20_2026-08-12_10-00-00.h264"

    payload = _payload(_upload(name))

    assert payload["s3_key"] == f"site/cam/{name}"
    assert payload["bucket_name"] == "videos"
    assert payload["original_filename"] == name
    assert payload["new_filename"] == name
    assert payload["camera_id"] == {"camera_id": 2, "project_id": 0, "site_id": 1}


def test_reports_no_time_yet() -> None:
    payload = _payload(_upload("otcamera_FR20_2026-08-12_10-00-00.h264"))

    assert payload["timestamp"] == ""
