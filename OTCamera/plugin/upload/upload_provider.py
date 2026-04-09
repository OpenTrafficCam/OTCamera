"""Upload backend provider."""

import logging

from OTCamera.config import Config, FtpUploadConfig, S3Config
from OTCamera.domain.upload import Upload
from OTCamera.plugin.upload.s3_upload import S3Upload

logger = logging.getLogger(__name__)


class UploadProvider:
    """Create upload backends from configuration."""

    @staticmethod
    def provide(config: Config) -> Upload | None:
        """Return an upload backend, or None when uploads are disabled."""
        if not config.server_upload.enable:
            logger.debug("Upload disabled")
            return None

        match config.server_upload.scheme:
            case "ftp":
                from OTCamera.plugin.upload.ftp_upload import FtpUpload

                ftp_config: FtpUploadConfig = config.server_upload.config
                return FtpUpload(
                    host=ftp_config.host,
                    port=ftp_config.port,
                    user=ftp_config.user,
                    password=ftp_config.password,
                    server_source=ftp_config.server_source,
                )

            case "s3":
                s3_config: S3Config = config.server_upload.config

                s3upload = S3Upload.from_config(s3_config)

                if s3_config.endpoint_url:
                    logger.info("Provided S3Uploader to custom endpoint %s, bucket name: %s" % (s3_config.endpoint_url, s3_config.bucket))
                else:
                    logger.info("Provided S3Uploader to AWS, bucket name: %s", s3_config.bucket)

                return s3upload

            case _:
                raise RuntimeError(f"invalid scheme: {config.server_upload.scheme}")
