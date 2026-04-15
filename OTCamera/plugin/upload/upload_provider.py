"""Upload backend provider."""

import logging

import boto3
from botocore.config import Config as Boto3Config

from OTCamera.config import Config
from OTCamera.domain.upload import Upload
from OTCamera.exceptions import BackendUnavailableError, UploadError
from OTCamera.plugin.upload.ftp_upload import FtpUpload
from OTCamera.plugin.upload.s3_upload import S3Upload

logger = logging.getLogger(__name__)


class UploadProvider:
    """Create an upload backend from configuration."""

    @staticmethod
    def provide(config: Config, skip_availability_check: bool = False) -> Upload | None:
        """Return the configured upload backend, or None when none is enabled.

        Raises:
            UploadError: If more than one upload backend is enabled simultaneously.
            BackendUnavailableError: When the upload backend is not available.
        """
        if config.ftp_upload and config.s3_upload:
            raise UploadError("Only one upload backend may be enabled at a time.")

        upload: Upload | None = None
        if config.ftp_upload:
            ftp = config.ftp_upload

            logger.debug("FTP upload backend enabled for host %s", ftp.host)
            upload = FtpUpload(
                host=ftp.host,
                port=ftp.port,
                user=ftp.user,
                password=ftp.password,
                server_source=ftp.server_source,
            )

        if config.s3_upload:
            s3config = config.s3_upload

            s3client = boto3.client(
                "s3",
                endpoint_url=s3config.endpoint_url,
                aws_access_key_id=s3config.access_key,
                aws_secret_access_key=s3config.secret_key,
                region_name=s3config.region,
                config=Boto3Config(
                    retries={"total_max_attempts": s3config.retry_max_attempts}
                ),
            )
            upload = S3Upload(
                s3client=s3client,
                bucket_name=s3config.bucket,
            )

        if upload is None:
            logger.info("No upload backend configured")
            return None

        logger.debug("Upload backend created: %s", type(upload).__name__)
        if not skip_availability_check and not upload.is_available():
            raise BackendUnavailableError("Upload backend is not available")

        return upload
