"""Upload backend provider."""

import logging

from OTCamera.config import Config
from OTCamera.domain.upload import Upload
from OTCamera.exceptions import UploadUnavailableError
from OTCamera.plugin.upload.s3_upload import S3Upload

logger = logging.getLogger(__name__)


class UploadProvider:
    """Create an upload backend from configuration."""

    @staticmethod
    def provide(config: Config, skip_availability_check: bool = False) -> Upload | None:
        """Return the configured upload backend, or None when none is enabled.

        Raises:
            ValueError: If more than one upload backend is enabled simultaneously.
            UploadUnavailableError: When the upload backend is not available.
        """
        ftp_enabled = config.ftp_upload.enable
        s3_enabled = config.s3_upload.enable

        if ftp_enabled and s3_enabled:
            raise ValueError(
                "Only one upload backend may be enabled at a time "
                "(ftp_upload.enable and s3_upload.enable are both true)."
            )

        upload = None
        if ftp_enabled:
            from OTCamera.plugin.upload.ftp_upload import FtpUpload

            ftp = config.ftp_upload
            logger.debug("FTP upload backend enabled for host %s", ftp.host)
            upload = FtpUpload(
                host=ftp.host,
                port=ftp.port,
                user=ftp.user,
                password=ftp.password,
                server_source=ftp.server_source,
            )

        if s3_enabled:
            upload = S3Upload.from_config(config.s3_upload)
            if config.s3_upload.endpoint_url:
                logger.info(
                    "S3 upload backend enabled: custom endpoint %s, bucket %s",
                    config.s3_upload.endpoint_url,
                    config.s3_upload.bucket,
                )
            else:
                logger.info(
                    "S3 upload backend enabled: AWS, bucket %s",
                    config.s3_upload.bucket,
                )

        if upload is None:
            logger.info("No upload backend configured")
            return None

        logger.debug("Upload backend created: %s", type(upload).__name__)
        if not skip_availability_check and not upload.is_available():
            raise UploadUnavailableError("Upload backend is not available")

        return upload
