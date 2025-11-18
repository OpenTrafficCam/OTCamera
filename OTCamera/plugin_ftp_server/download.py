from ftplib import FTP
from pathlib import Path

from OTCloud.plugin_ftp_server.errors import FtpDownloadError, FtpFileNotFoundError
from OTCloud.plugin_ftp_server.navigate import FtpNavigateToDirectory


class FtpDownload:
    """Utility to download a single file via FTP.

    The instance operates on an already connected and authenticated
    ``ftplib.FTP`` client. It first navigates to the directory of the remote
    file and then retrieves it into a local destination path, creating parent
    directories as needed.
    """

    def __init__(self, navigate_to_dir: FtpNavigateToDirectory):
        self._navigate_to_dir = navigate_to_dir

    def download(self, client: FTP, source: Path, dest: Path) -> None:
        """Download a file from an FTP server to a local path.

        Args:
            client (ftplib.FTP): A connected and authenticated FTP client to
                use for the transfer.
            source (Path): The remote file path to download. This can be absolute or
                relative to the client's current directory.
            dest (Path): The local filesystem path where the file will be written.
                Parent directories will be created if missing.

        Raises:
            FtpTraversalError: If navigating to the remote file's directory fails.
            Exception: Any exceptions raised by ``ftplib.FTP.retrbinary`` may propagate.
        """
        self._navigate_to_dir.navigate(client, directory=source.parent)
        self._download(client, source=source, dest=dest)

    def _download(self, client: FTP, source: Path, dest: Path) -> None:
        """Retrieve a remote file into a local destination.

        Args:
            client (ftplib.FTP): The FTP client used for ``retrbinary``.
            source (Path): The remote file to retrieve (the client should already be in
                the correct directory).
            dest (Path): The local file path where data will be written.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)

        if source.name not in client.nlst():
            raise FtpFileNotFoundError(f"File '{source}' not found on FTP server")

        try:
            with open(dest, "wb") as f:
                client.retrbinary(f"RETR {source.name}", f.write)
        except Exception as cause:
            raise FtpDownloadError(
                f"Unable to download file: '{source}' to '{dest}'"
            ) from cause
