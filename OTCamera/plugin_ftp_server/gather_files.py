from ftplib import FTP
from pathlib import Path

from OTCloud.plugin_ftp_server.navigate import FtpNavigateToDirectory


class FtpGatherFiles:
    """FTP convenience class for listing files in a remote FTP directory.

    Args:
        navigate_to_dir (FtpNavigateToDirectory): convenience class to navigate to a
            directory on a FTP server.
    """

    def __init__(self, navigate_to_dir: FtpNavigateToDirectory) -> None:
        self._navigate_to_dir = navigate_to_dir

    def gather(self, client: FTP, folder: Path) -> set[Path]:
        """List entries in the given remote FTP folder.

        Args:
            client (FTP): An active and authenticated ``ftplib.FTP`` client instance.
            folder (Path): Remote directory to gather entries from.

        Returns:
            set[Path]: listed entries in the folder.
        """
        self._navigate_to_dir.navigate(client, folder)
        files_in_folder = client.nlst()
        return {Path(_file) for _file in files_in_folder}
