from ftplib import FTP
from pathlib import Path
from typing import Iterable


from OTCamera.application.files import PathComponentReplacer
from OTCamera.application.logger import logger
from OTCamera.plugin_ftp_server.config import FtpServerConfig
from OTCamera.plugin_ftp_server.connect import FtpsServerConnect
from OTCamera.plugin_ftp_server.errors import FtpUploadError
from OTCamera.plugin_ftp_server.upload import FtpUpload


class UploadResultFilesToFtpServer:
    """Use case for uploading result files to an FTP/FTPS server.


    Args:
        ftp_server_connect (FtpsServerConnect): Factory to create an
            authenticated ftplib.FTP/FTPS client using the provided server
            configuration.
        ftp_upload (FtpUpload): Component that performs the actual file upload
            to the server.
        to_ftp_source_replacer (PathComponentReplacer): Translates a local path
            into its corresponding remote FTP path (e.g., by swapping root
            components).
        ftp_server_config (FtpServerConfig): Configuration object with the
            server connection settings.
    """

    def __init__(
        self,
        ftp_server_connect: FtpsServerConnect,
        ftp_upload: FtpUpload,
        to_ftp_source_replacer: PathComponentReplacer,
        ftp_server_config: FtpServerConfig,
    ) -> None:
        self._ftp_server_connect = ftp_server_connect
        self._ftp_upload = ftp_upload
        self._to_ftp_source_replacer = to_ftp_source_replacer
        self._ftp_server_config = ftp_server_config

    def upload(self, result_files: Iterable[Path]) -> None:
        """Upload files to the FTP server.

        The method opens a connection using the configured FTP/FTPS settings,
        derives result file paths from the provided OTVision config, translates
        each local path to its remote counterpart, uploads the files, and
        finally closes the connection.

        Args:
            result_files (Iterable[Path]): the path to the result file to upload.
        """
        try:
            client = self._ftp_server_connect.connect_with_config(
                self._ftp_server_config
            )
            failed_uploads: list[Path] = []
            for result_file in result_files:
                try:
                    self._do_upload(client, result_file)
                except Exception as cause:
                    failed_uploads.append(result_file)
                    logger().error(f"Failed to upload {result_file}: {cause}")
            if failed_uploads:
                error_msg = (
                    f"Failed to upload {len(failed_uploads)} result file(s): "
                    f"{failed_uploads}"
                )
                logger().warning(error_msg)
                raise FtpUploadError(error_msg)

        finally:
            client.close()

    def _do_upload(self, client: FTP, file_on_user_source: Path) -> None:
        file_on_ftp_source = self._to_ftp_source_replacer.replace(file_on_user_source)
        self._ftp_upload.upload(
            client,
            source=file_on_user_source,
            dest=file_on_ftp_source,
        )

