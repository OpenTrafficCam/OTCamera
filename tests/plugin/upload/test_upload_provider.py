import pytest
from botocore.stub import Stubber
from pydantic import ValidationError

from OTCamera.config import Config, FtpUploadConfig, S3Config
from OTCamera.plugin.upload.s3_upload import S3Upload
from OTCamera.plugin.upload.upload_provider import UploadProvider


def test_provide_returns_none_when_no_upload_configured() -> None:
    assert UploadProvider.provide(Config()) is None


def test_ftp_upload_config_required_when_upload_is_ftp() -> None:
    with pytest.raises(ValidationError):
        Config(upload="ftp")


def test_s3_upload_config_required_when_upload_is_s3() -> None:
    with pytest.raises(ValidationError):
        Config(upload="s3")


def test_provide_ignores_ftp_config_when_upload_not_set() -> None:
    config = Config()
    config.ftp_upload = FtpUploadConfig(
        host="localhost", port=21, user="user", password="pass"
    )
    assert UploadProvider.provide(config) is None


def test_s3_client_accepts_bucket_of_other_tenant() -> None:
    tenant_bucket = "other-tenant:bucket"
    config = Config(
        upload="s3",
        s3_upload=S3Config(
            access_key="foo",
            secret_key="bar",
            bucket=tenant_bucket,
            endpoint_url="http://localhost:9000",
            region="us-east-1",
        ),
    )
    upload = UploadProvider.provide(config)
    assert isinstance(upload, S3Upload)

    with Stubber(upload.client) as stubber:
        stubber.add_response("head_object", {}, {"Bucket": tenant_bucket, "Key": "key"})
        upload.client.head_object(Bucket=tenant_bucket, Key="key")
        stubber.assert_no_pending_responses()


def test_provide_ignores_s3_config_when_upload_not_set() -> None:
    config = Config()
    config.s3_upload = S3Config(access_key="foo", secret_key="bar", bucket="bucket")
    assert UploadProvider.provide(config) is None
