from pathlib import Path

from OTCamera.application.serialization import Deserializer
from OTCamera.plugin_ftp_server.config import FtpServerConfig, Url


class IncompleteFtpServerConfigError(Exception):
    pass


class FtpServerConfigKeys:
    FTP_SERVER = "ftp-server"
    SCHEME = "scheme"
    HOST = "host"
    PORT = "port"
    USER = "user"
    PASSWORD = "password"
    OTCLOUD_SOURCE = "otcloud-source"
    USER_SOURCE = "user-source"
    SERVER_SOURCE = "server-source"


class FtpServerConfigParser:
    def __init__(self, deserializer: Deserializer):
        self._deserializer = deserializer

    def parse(self, config_file: Path) -> FtpServerConfig | None:
        raw_data = self._deserializer.from_file(config_file)
        return self.parse_from_dict(raw_data)

    def parse_from_dict(self, data: dict) -> FtpServerConfig | None:
        if ftp_server_data := data.get(FtpServerConfigKeys.FTP_SERVER):
            try:
                scheme = ftp_server_data[FtpServerConfigKeys.SCHEME]
                host = ftp_server_data[FtpServerConfigKeys.HOST]
                port = int(ftp_server_data[FtpServerConfigKeys.PORT])
                user = ftp_server_data[FtpServerConfigKeys.USER]
                password = ftp_server_data[FtpServerConfigKeys.PASSWORD]
                user_source = ftp_server_data[FtpServerConfigKeys.USER_SOURCE]
                server_source = ftp_server_data[FtpServerConfigKeys.SERVER_SOURCE]
                otcloud_source = ftp_server_data[FtpServerConfigKeys.OTCLOUD_SOURCE]
                return FtpServerConfig(
                    url=Url(scheme=scheme, host=host, port=port),
                    user=user,
                    password=password,
                    otcloud_source=otcloud_source,
                    user_source=user_source,
                    server_source=server_source,
                )
            except KeyError as cause:
                raise IncompleteFtpServerConfigError(
                    f"Missing key {cause} in ftp-server section of config file."
                ) from cause
        return None
