from ftplib import FTP, FTP_TLS

from OTCamera.plugin_ftp_server.config import FtpServerConfig
from OTCamera.plugin_ftp_server.errors import FtpConnectionError

DEFAULT_TIMEOUT = 30


class FtpsServerConnect:
    """Helper for connecting to an FTPS server.

    The instance constructs an ``ftplib.FTP_TLS`` client, connects to the
    provided host and port, and logs in with explicit TLS enabled.
    """

    def connect(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> FTP:
        """Create and return an authenticated FTPS client.

        Args:
            host (str): Hostname or IP address of the FTPS server.
            port (int): TCP port of the FTPS service (typically 21).
            user (str): Username for authentication.
            password (str): Password for authentication.
            timeout (int): Timeout in seconds for the connection.

        Returns:
            ftplib.FTP: A connected and authenticated ``FTP_TLS`` client.

        Raises:
            FtpConnectionError: If connecting or logging in to the server
                fails. The original exception will be attached as the cause.
        """
        try:
            ftp = FTP_TLS()
            ftp.connect(host=host, port=port, timeout=timeout)
            ftp.login(user=user, passwd=password, secure=True)
            return ftp
        except Exception as cause:
            raise FtpConnectionError("Unable to connect to FTP server") from cause

    def connect_with_config(
        self, config: FtpServerConfig, timeout: int = DEFAULT_TIMEOUT
    ) -> FTP:
        return self.connect(
            host=config.url.host,
            port=config.url.port,
            user=config.user,
            password=config.password,
            timeout=timeout,
        )
