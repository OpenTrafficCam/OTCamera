"""Upload backend provider."""

import logging
from pathlib import Path

import boto3
from botocore.config import Config as Boto3Config

from OTCamera.config import Config, FtpUploadConfig, S3Config
from OTCamera.domain.upload import Upload
from OTCamera.plugin.upload.ftp_upload import FtpUpload
from OTCamera.plugin.upload.s3_upload import S3Upload

logger = logging.getLogger(__name__)


class UploadProvider:
    """Create an upload backend from configuration."""

    @staticmethod
    def _create_ftp_upload(ftp: FtpUploadConfig) -> FtpUpload:
        logger.debug("FTP upload backend enabled for host %s", ftp.host)
        return FtpUpload(
            host=ftp.host,
            port=ftp.port,
            user=ftp.user,
            password=ftp.password,
            server_source=ftp.server_source,
        )

    @staticmethod
    def _create_s3_upload(
        s3config: S3Config,
    ) -> S3Upload:
        logger.debug("S3 upload backend enabled for bucket %s", s3config.bucket)
        s3client = boto3.client(
            "s3",
            endpoint_url=s3config.endpoint_url,
            aws_access_key_id=s3config.access_key,
            aws_secret_access_key=s3config.secret_key,
            region_name=s3config.region,
            config=Boto3Config(
                # One attempt only: retrying is the backlog controller's job, and
                # a second layer of retries here would only add its waits to the
                # controller's before the failure is reported.
                retries={"total_max_attempts": 1},
                connect_timeout=s3config.connect_timeout,
                read_timeout=s3config.read_timeout,
            ),
        )
        return S3Upload(
            s3client=s3client,
            bucket_name=s3config.bucket,
            key_prefix=s3config.key_prefix,
        )

    @staticmethod
    def provide(config: Config) -> Upload | None:
        """Return the configured upload backend, if there is one.

        Configuring no backend is valid: the camera records and keeps its
        footage on the card.

        Args:
            config (Config): The parsed user configuration.

        Returns:
            Upload | None: The configured backend, or None when none is
                configured.
        """
        if config.upload == "ftp":
            assert config.ftp_upload is not None
            return UploadProvider._create_ftp_upload(config.ftp_upload)

        if config.upload == "s3":
            assert config.s3_upload is not None
            return UploadProvider._create_s3_upload(
                config.s3_upload,
            )

        logger.info(
            "No upload backend configured; recordings are kept in %s until "
            "space is needed",
            Path(config.video.dir) / "pending",
        )
        return None
