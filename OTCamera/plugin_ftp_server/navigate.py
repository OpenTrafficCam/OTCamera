from ftplib import FTP
from pathlib import Path

from OTCloud.plugin_ftp_server.errors import FtpTraversalError


class FtpNavigateToDirectory:
    def navigate(self, client: FTP, directory: Path) -> None:
        """Change the client's working directory step by step.

        Args:
            client (ftplib.FTP): The FTP client used to issue ``cwd`` calls.
            directory (Path): The directory containing the desired file.
                Its parts will be traversed sequentially.

        Raises:
            FtpTraversalError: If any step in the traversal fails.
            FtpFileNotFoundError: If the file doesn't exist on the FTP server.
        """
        client.cwd("/")
        try:
            for path in directory.parts:
                client.cwd(path)
        except Exception:
            raise FtpTraversalError(f"Unable to navigate to directory: {directory}")
