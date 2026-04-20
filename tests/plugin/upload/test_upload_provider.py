import pytest
from pydantic import ValidationError

from OTCamera.config import Config, FtpUploadConfig, S3Config
from OTCamera.plugin.upload.upload_provider import UploadProvider


def test_provide_returns_none_when_no_upload_configured(
    default_config: Config,
) -> None:
    assert UploadProvider.provide(default_config) is None


def test_ftp_upload_config_required_when_upload_is_ftp() -> None:
    with pytest.raises(ValidationError):
        Config(upload="ftp")


def test_s3_upload_config_required_when_upload_is_s3() -> None:
    with pytest.raises(ValidationError):
        Config(upload="s3")


def test_provide_ignores_ftp_config_when_upload_not_set(
    default_config: Config,
) -> None:
    default_config.ftp_upload = FtpUploadConfig(
        host="localhost", port=21, user="user", password="pass"
    )
    assert UploadProvider.provide(default_config) is None


def test_provide_ignores_s3_config_when_upload_not_set(
    default_config: Config,
) -> None:
    default_config.s3_upload = S3Config(
        access_key="foo", secret_key="bar", bucket="bucket"
    )
    assert UploadProvider.provide(default_config) is None
