"""FTPS upload backend."""

import logging
from ftplib import FTP_TLS
from pathlib import Path

from OTCamera.domain.upload import Upload
from OTCamera.plugin.upload.exceptions import FileUploadError

logger = logging.getLogger(__name__)


class FtpUpload(Upload):
    """Upload files via FTPS to a remote server."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        server_source: str = "/",
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._server_source = server_source

    def upload(self, file_path: str) -> None:
        """Upload a local file to the configured FTPS target directory."""
        source = Path(file_path)
        destination = Path(self._server_source) / source.name
        logger.debug(
            "Uploading %s (%d bytes) to %s",
            source,
            source.stat().st_size,
            destination,
        )

        client = self._connect()
        try:
            self._navigate_to_dir(client, destination.parent)
            with open(source, "rb") as file_handle:
                client.storbinary(f"STOR {destination.name}", file_handle)
        except Exception as exc:
            raise FileUploadError(f"Upload failed for {source.name}: {exc}") from exc
        finally:
            client.close()

        logger.info("Uploaded %s", source.name)

    def is_available(self) -> bool:
        """Return whether the FTPS endpoint is reachable."""
        try:
            client = self._connect()
        except Exception:
            return False
        client.close()
        return True

    def _connect(self) -> FTP_TLS:
        """Connect and authenticate against the FTPS endpoint."""
        ftp = FTP_TLS()
        ftp.connect(self._host, self._port, timeout=30)
        ftp.login(self._user, self._password)
        ftp.prot_p()
        return ftp

    def _navigate_to_dir(self, client: FTP_TLS, path: Path) -> None:
        """Create and enter the destination directory path."""
        client.cwd("/")
        for part in path.parts:
            if part == "/":
                continue
            try:
                client.cwd(part)
            except Exception:
                client.mkd(part)
                client.cwd(part)
