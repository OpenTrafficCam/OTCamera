from ftplib import FTP

from OTCamera.plugin_ftp_server.config import FtpServerConfig
from OTCamera.plugin_ftp_server.connect import FtpsServerConnect


class ConnectToFtpServer:
    """Use case to connect to an FTP server."""

    def __init__(
        self,
        ftp_server_connect: FtpsServerConnect,
        ftp_server_config: FtpServerConfig,
    ) -> None:
        self._ftp_server_connect = ftp_server_connect
        self._ftp_server_config = ftp_server_config

    def connect(self) -> FTP:
        """Connect to the FTP server.

        Returns:
            FTP: The connected FTP client.
        """
        return self._ftp_server_connect.connect_with_config(self._ftp_server_config)
