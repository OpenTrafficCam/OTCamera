from ftplib import FTP
from pathlib import Path

from OTCamera.plugin_ftp_server.errors import FtpTraversalError, FtpUploadError


class FtpUpload:
    """Utility to upload a single file via FTP.

    The instance operates on an already connected and authenticated ftplib.FTP
    client. It first navigates to (and creates, if necessary) the destination
    directory on the server, then stores the file using the STOR command.
    """

    def upload(self, client: FTP, source: Path, dest: Path) -> None:
        """Upload a local file to a remote FTP path.

        Args:
            client (ftplib.FTP): Connected and authenticated FTP client used for
                the transfer.
            source (Path): Local file path to upload. The file must exist and be
                readable.
            dest (Path): Remote target path (including filename). Parent directories
                will be traversed and created if missing.

        Raises:
            FtpTraversalError: If navigating to or creating destination directories
                fails.
            FtpUploadError: If the upload operation fails.
        """
        self._navigate_to_dir(client, dest.parent)
        self._do_upload(client, source=source, dest=dest)

    def _navigate_to_dir(self, client: FTP, directory: Path) -> None:
        client.cwd("/")
        try:
            for dir_name in directory.parts:
                try:
                    client.cwd(dir_name)
                except Exception:
                    # directory does not exist, create it
                    client.mkd(dir_name)
                    client.cwd(dir_name)
        except Exception as cause:
            raise FtpTraversalError(
                f"Unable to navigate to directory: {directory}"
            ) from cause

    def _do_upload(self, client: FTP, source: Path, dest: Path) -> None:
        try:
            with open(source, "rb") as f:
                client.storbinary(f"STOR {dest.name}", f)
        except Exception as cause:
            raise FtpUploadError(
                f"Unable to upload file: '{source}' to '{dest}'"
            ) from cause

    def _create_dir(self, client: FTP, dir_name: str) -> None:
        client.mkd(dir_name)
