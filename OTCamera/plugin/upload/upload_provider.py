"""Upload backend provider."""

import logging

from OTCamera.config import Config
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadProvider:
    """Create upload backends from configuration."""

    @staticmethod
    def provide(config: Config) -> Upload | None:
        """Return an upload backend, or None when uploads are disabled."""
        if not config.server_upload.enable:
            logger.debug("Upload disabled")
            return None

        from OTCamera.plugin.upload.ftp_upload import FtpUpload

        server_upload = config.server_upload
        return FtpUpload(
            host=server_upload.host,
            port=server_upload.port,
            user=server_upload.user,
            password=server_upload.password,
            server_source=server_upload.server_source,
        )
