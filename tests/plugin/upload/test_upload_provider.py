import pytest

from OTCamera.config import Config, FtpUploadConfig, S3Config
from OTCamera.exceptions import UploadError
from OTCamera.plugin.upload.upload_provider import UploadProvider


def test_only_one_provider_can_be_active() -> None:
    config = Config()

    config.ftp_upload = FtpUploadConfig(
        host="localhost",
        port=21,
        user="user",
        password="pass",
        directory="/upload",
        skip_availability_check=True,
    )

    config.s3_upload = S3Config(access_key="foo", secret_key="bar", bucket="bucket")

    with pytest.raises(UploadError):
        UploadProvider().provide(config)
