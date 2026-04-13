"""OTCamera configuration models and YAML parsing."""

import logging
import socket
from pathlib import Path
from typing import Any

try:
    from yaml import CSafeLoader as SafeLoader  # type: ignore[attr-defined]
except ImportError:
    from yaml import SafeLoader  # type: ignore[assignment]

import yaml
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

# YAML interprets values like `off`, `on`, `yes`, `no` as booleans.
# This type coerces any such value to str before pydantic validates it.
StrFromYaml = Annotated[str, BeforeValidator(str)]

logger = logging.getLogger(__name__)


class RecordingConfig(BaseModel):
    """Recording schedule and disk-space settings."""

    start_hour: int = 6
    end_hour: int = 22
    interval_length: int = 15
    num_intervals: int = 0
    min_free_space: int = 1


class CameraConfig(BaseModel):
    """Camera hardware and ISP settings."""

    fps: int = 20
    resolution: tuple[int, int] = (2304, 1296)
    exposure_mode: StrFromYaml = "nightpreview"
    drc_strength: StrFromYaml = "high"
    rotation: int = 180
    awb_mode: StrFromYaml = "greyworld"
    meter_mode: StrFromYaml = "average"

    @field_validator("resolution", mode="before")
    @classmethod
    def _parse_resolution(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return (int(v["width"]), int(v["height"]))
        return v


class PreviewConfig(BaseModel):
    """Preview capture and preview upload settings."""

    path: StrFromYaml = "~/OTCamera/webfiles/preview.jpg"
    format: StrFromYaml = "jpeg"
    interval: int = 5
    send_to_external: bool = False
    url: StrFromYaml = "http://localhost:5000/projects/0/sites/1/cameras/2/current_frame"


class S3Config(BaseModel):
    """Config for S3-compatible object storage."""

    enable: bool = False
    access_key: StrFromYaml | None = None
    secret_key: StrFromYaml | None = None
    bucket: StrFromYaml | None = None
    endpoint_url: StrFromYaml | None = None
    region: StrFromYaml | None = None
    retry_max_attempts: int = 5

    @model_validator(mode="after")
    def _require_credentials_when_enabled(self) -> "S3Config":
        if self.enable:
            missing = [
                f for f in ("access_key", "secret_key", "bucket")
                if getattr(self, f) is None
            ]
            if missing:
                raise ValueError(
                    f"Fields required when s3.enable is true: {missing}"
                )
        return self


class FtpUploadConfig(BaseModel):
    """FTP upload settings."""

    enable: bool = False
    host: StrFromYaml | None = None
    port: int = 21
    user: StrFromYaml | None = None
    password: StrFromYaml | None = None
    server_source: StrFromYaml = "/"

    @model_validator(mode="after")
    def _require_credentials_when_enabled(self) -> "FtpUploadConfig":
        if self.enable:
            missing = [f for f in ("host", "user", "password") if getattr(self, f) is None]
            if missing:
                raise ValueError(
                    f"Fields required when ftp_upload.enable is true: {missing}"
                )
        return self


class EncoderConfig(BaseModel):
    """H.264 encoder settings."""

    profile: StrFromYaml = "high"
    level: StrFromYaml = "4"
    bitrate: int = 600000
    quality: int = 30


class VideoConfig(BaseModel):
    """Recorded video output settings."""

    dir: StrFromYaml = "~/videos/"
    format: StrFromYaml = "h264"
    resolution: tuple[int, int] = (800, 600)
    encoder: EncoderConfig = Field(default_factory=EncoderConfig)

    @field_validator("resolution", mode="before")
    @classmethod
    def _parse_resolution(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return (int(v["width"]), int(v["height"]))
        return v


class WifiConfig(BaseModel):
    """Wi-Fi access point settings."""

    delay: int = 900


class HardwareConfig(BaseModel):
    """Hardware feature toggles and board selection."""

    pcb_version: StrFromYaml = "v2"
    use_leds: bool = False
    use_buttons: bool = False
    use_adc: bool = False


class MsTeamsConfig(BaseModel):
    """MS Teams logging webhook settings."""

    enable: bool = False
    url: StrFromYaml | None = None
    max_failed_send_attempts: int = 2

    @model_validator(mode="after")
    def _require_url_when_enabled(self) -> "MsTeamsConfig":
        if self.enable and self.url is None:
            raise ValueError("msteams.url is required when msteams.enable is true")
        return self


class AdcConfig(BaseModel):
    """Voltage thresholds used by power monitoring."""

    threshold_external_power: float = 2.5
    threshold_low_battery: float = 3.3


class Config(BaseModel):
    """Top-level OTCamera configuration."""

    debug_mode: bool = False
    relay_server: bool = False
    prefix: StrFromYaml = Field(default_factory=socket.gethostname)
    recording: RecordingConfig = Field(default_factory=RecordingConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    preview: PreviewConfig = Field(default_factory=PreviewConfig)
    ftp_upload: FtpUploadConfig = Field(default_factory=FtpUploadConfig)
    s3_upload: S3Config = Field(default_factory=S3Config)
    delete_after_upload: bool = False
    video: VideoConfig = Field(default_factory=VideoConfig)
    wifi: WifiConfig = Field(default_factory=WifiConfig)
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    msteams: MsTeamsConfig = Field(default_factory=MsTeamsConfig)
    adc: AdcConfig = Field(default_factory=AdcConfig)
    template_html_path: StrFromYaml = "~/OTCamera/webfiles/template.html"
    index_html_path: StrFromYaml = "~/OTCamera/webfiles/index.html"
    offline_html_path: StrFromYaml = "~/OTCamera/webfiles/offline.html"
    num_log_files_html: int = 2
    usb_mount_point: StrFromYaml = "~/mnt/usb"
    usb_device: StrFromYaml = "/dev/sda1"

    def resolve_paths(self) -> None:
        """Resolve path-valued settings to absolute paths."""
        self.video.dir = _resolve_path(self.video.dir)
        self.preview.path = _resolve_path(self.preview.path)
        self.template_html_path = _resolve_path(self.template_html_path)
        self.index_html_path = _resolve_path(self.index_html_path)
        self.offline_html_path = _resolve_path(self.offline_html_path)
        self.usb_mount_point = _resolve_path(self.usb_mount_point)


def parse_user_config(config_file: str) -> Config:
    """Parse a YAML config file and return a Config instance."""
    config_path = Path(config_file).expanduser().resolve()
    try:
        with open(config_path, mode="rb") as file_handle:
            data = yaml.load(file_handle, Loader=SafeLoader) or {}
    except FileNotFoundError:
        logger.warning("No user config found at %s, using defaults.", config_path)
        data = {}
    config = Config.model_validate(data)
    config.resolve_paths()
    return config


def _resolve_path(path: str) -> str:
    """Resolve a configured path to an absolute path."""
    return str(Path(path).expanduser().resolve())
