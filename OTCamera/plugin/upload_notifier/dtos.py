"""Payload DTOs for upload notification messages."""

from dataclasses import dataclass


@dataclass
class CameraIdDto:
    camera_id: int
    project_id: int
    site_id: int


@dataclass
class S3FileUploadedEvent:
    """Event representing a file uploaded to S3 storage.

    This is the infrastructure-layer representation of a file upload event
    that includes S3-specific storage details. This class bridges the gap
    between S3 storage and the domain model.

    Attributes:
        s3_key (str): The S3 object key (path) where the file is stored.
        camera_id (CameraIdDto): Identifier of the camera that captured the file.
        timestamp (str): timestamp in ISO format. See datetime.isoformat().
        original_filename (str): The original name of the file before processing.
        new_filename (str): The new name assigned to the file after upload.
        bucket_name (str | None): Optional S3 bucket name if different from default.
    """

    s3_key: str
    camera_id: CameraIdDto
    timestamp: str
    original_filename: str
    new_filename: str
    bucket_name: str | None = None
