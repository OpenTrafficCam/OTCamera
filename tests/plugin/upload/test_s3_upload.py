from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from OTCamera.plugin.upload.exceptions import FileUploadError
from OTCamera.plugin.upload.s3_upload import S3Upload


class FakeS3Client:
    """An S3 client whose `put_object` raises a configured exception."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def put_object(self, *args: Any, **kwargs: Any) -> None:
        raise self._error


def _client_error(code: str, status: int) -> ClientError:
    response: Any = {
        "Error": {"Code": code, "Message": "denied"},
        "ResponseMetadata": {"HTTPStatusCode": status},
    }
    return ClientError(response, "PutObject")


def test_refusal_from_a_real_client_carries_the_error_code(tmp_path: Path) -> None:
    """A refusal must reach `upload` as a `ClientError`, not wrapped.

    boto3's `upload_file` wraps refusals in `S3UploadFailedError`, which
    hides the error code. This test runs against a real client so a change
    back to a wrapping transfer method fails here, not in the field.
    """
    video = tmp_path / "video.h264"
    video.write_bytes(b"x")
    client = boto3.client(
        "s3",
        region_name="eu-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    stubber = Stubber(client)
    stubber.add_client_error(
        "put_object",
        service_error_code="AccessDenied",
        service_message="denied",
        http_status_code=403,
    )
    upload = S3Upload(client, "bucket")

    with stubber, pytest.raises(FileUploadError) as exc_info:
        upload.upload(video)

    assert exc_info.value.error_code == "AccessDenied"
    assert exc_info.value.status_code == 403


def test_client_error_surfaces_boto_error_code(tmp_path: Path) -> None:
    video = tmp_path / "video.h264"
    video.write_bytes(b"x")
    upload = S3Upload(FakeS3Client(_client_error("AccessDenied", 403)), "bucket")

    with pytest.raises(FileUploadError) as exc_info:
        upload.upload(video)

    assert exc_info.value.error_code == "AccessDenied"
    assert exc_info.value.status_code == 403


def test_client_error_without_details_leaves_fields_none(tmp_path: Path) -> None:
    video = tmp_path / "video.h264"
    video.write_bytes(b"x")
    error = ClientError({}, "PutObject")
    upload = S3Upload(FakeS3Client(error), "bucket")

    with pytest.raises(FileUploadError) as exc_info:
        upload.upload(video)

    assert exc_info.value.error_code is None
    assert exc_info.value.status_code is None


def test_os_error_reports_the_unreadable_file(tmp_path: Path) -> None:
    video = tmp_path / "video.h264"
    video.write_bytes(b"x")
    upload = S3Upload(FakeS3Client(OSError("input/output error")), "bucket")

    with pytest.raises(FileUploadError) as exc_info:
        upload.upload(video)

    assert "video.h264" in str(exc_info.value)
    assert exc_info.value.error_code is None


def test_unexpected_error_carries_no_error_code(tmp_path: Path) -> None:
    video = tmp_path / "video.h264"
    video.write_bytes(b"x")
    upload = S3Upload(FakeS3Client(RuntimeError("boom")), "bucket")

    with pytest.raises(FileUploadError) as exc_info:
        upload.upload(video)

    assert exc_info.value.error_code is None
    assert exc_info.value.status_code is None
