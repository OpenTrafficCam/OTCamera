from dataclasses import dataclass


@dataclass(frozen=True)
class Url:
    scheme: str
    host: str
    port: int

    def get_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"


@dataclass(frozen=True)
class FtpServerConfig:
    url: Url
    user: str
    password: str
