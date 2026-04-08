"""OTCamera configuration dataclasses and YAML parsing."""

import logging
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

try:
    from yaml import CSafeLoader as SafeLoader  # type: ignore[attr-defined]
except ImportError:
    from yaml import SafeLoader  # type: ignore[assignment]

import yaml

logger = logging.getLogger(__name__)


@dataclass
class RecordingConfig:
    """Recording schedule and disk-space settings."""

    start_hour: int = 6
    end_hour: int = 22
    interval_length: int = 15
    num_intervals: int = 0
    min_free_space: int = 1


@dataclass
class CameraConfig:
    """Camera hardware and ISP settings."""

    fps: int = 20
    resolution: tuple[int, int] = (2304, 1296)
    exposure_mode: str = "nightpreview"
    drc_strength: str = "high"
    rotation: int = 180
    awb_mode: str = "greyworld"
    meter_mode: str = "average"


@dataclass
class PreviewConfig:
    """Preview capture and preview upload settings."""

    path: str = "~/OTCamera/webfiles/preview.jpg"
    format: str = "jpeg"
    interval: int = 5
    send_to_external: bool = False
    url: str = "http://localhost:5000/projects/0/sites/1/cameras/2/current_frame"


@dataclass
class FtpUploadConfig:
    host: str = "localhost"
    port: int = 21
    user: str = "user"
    password: str = "password"
    server_source: str = "/"


@dataclass
class S3Config:
    """Configuration for S3-compatible object storage.

    Attributes:
        endpoint_url (str | None): S3 endpoint URL (None for AWS S3).
        access_key (str): S3 access key for authentication.
        secret_key (str): S3 secret key for authentication.
        bucket (str): S3 bucket name.
        region (str | None): AWS region (None if not applicable).
    """

    endpoint_url: str | None = None
    access_key: str = ""
    secret_key: str = ""
    bucket: str = ""
    region: str | None = None


@dataclass
class ServerUploadConfig:
    """Remote upload settings."""

    enable: bool = False
    scheme: str = "s3"
    config: FtpUploadConfig | S3Config | None = None


@dataclass
class VideoConfig:
    """Recorded video output settings."""

    dir: str = "~/videos/"
    format: str = "h264"
    resolution: tuple[int, int] = (800, 600)
    h264_profile: str = "high"
    h264_level: str = "4"
    h264_bitrate: int = 600000
    h264_quality: int = 30


@dataclass
class WifiConfig:
    """Wi-Fi access point settings."""

    delay: int = 900


@dataclass
class HardwareConfig:
    """Hardware feature toggles and board selection."""

    pcb_version: str = "v2"
    use_leds: bool = False
    use_buttons: bool = False
    use_adc: bool = False


@dataclass
class MsTeamsConfig:
    """MS Teams logging webhook settings."""

    enable: bool = False
    url: str | None = None
    max_failed_send_attempts: int = 2


@dataclass
class AdcConfig:
    """Voltage thresholds used by power monitoring."""

    threshold_external_power: float = 2.5
    threshold_low_battery: float = 3.3


@dataclass
class Config:
    """Top-level OTCamera configuration."""

    debug_mode_on: bool = False
    use_relay: bool = False
    prefix: str = field(default_factory=socket.gethostname)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    preview: PreviewConfig = field(default_factory=PreviewConfig)
    server_upload: ServerUploadConfig = field(default_factory=ServerUploadConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    wifi: WifiConfig = field(default_factory=WifiConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    msteams: MsTeamsConfig = field(default_factory=MsTeamsConfig)
    adc: AdcConfig = field(default_factory=AdcConfig)
    template_html_path: str = "~/OTCamera/webfiles/template.html"
    index_html_path: str = "~/OTCamera/webfiles/index.html"
    offline_html_path: str = "~/OTCamera/webfiles/offline.html"
    num_log_files_html: int = 2
    usb_mount_point: str = "~/mnt/usb"
    usb_device: str = "/dev/sda1"

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
    config = Config()

    try:
        with open(config_path, mode="rb") as file_handle:
            loaded_data = yaml.load(file_handle, Loader=SafeLoader)
    except FileNotFoundError:
        logger.warning("No user config found at %s, using defaults.", config_path)
        config.resolve_paths()
        return config

    data = _as_section(loaded_data)
    if not data:
        config.resolve_paths()
        return config

    _parse_general_config(config, data)
    _parse_recording_config(config, _get_section(data, "recording"))
    _parse_camera_config(config, _get_section(data, "camera"))
    _parse_preview_config(config, _get_section(data, "preview"))
    _parse_server_upload_config(config, _get_section(data, "server_upload"))
    _parse_video_config(config, _get_section(data, "video"))
    _parse_wifi_config(config, _get_section(data, "wifi"))
    _parse_hardware_config(config, _get_section(data, "hardware"))
    _parse_msteams_config(config, _get_section(data, "msteams"))
    _parse_adc_config(config, _get_section(data, "adc"))

    config.resolve_paths()
    return config


def _parse_general_config(config: Config, data: Mapping[str, Any]) -> None:
    debug_mode = _get_section(data, "debug_mode")
    relay_server = _get_section(data, "relay_server")
    config.debug_mode_on = _read_bool(
        debug_mode,
        "enable",
        config.debug_mode_on,
    )
    config.use_relay = _read_bool(relay_server, "enable", config.use_relay)


def _parse_recording_config(config: Config, data: Mapping[str, Any]) -> None:
    recording = config.recording
    recording.start_hour = _read_int(data, "start_hour", recording.start_hour)
    recording.end_hour = _read_int(data, "end_hour", recording.end_hour)
    recording.interval_length = _read_int(
        data,
        "interval_length",
        recording.interval_length,
    )
    recording.num_intervals = _read_int(data, "num_intervals", recording.num_intervals)
    recording.min_free_space = _read_int(
        data,
        "min_free_space",
        recording.min_free_space,
    )


def _parse_camera_config(config: Config, data: Mapping[str, Any]) -> None:
    camera = config.camera
    camera.fps = _read_int(data, "fps", camera.fps)
    camera.resolution = _read_resolution(data, "resolution", camera.resolution)
    camera.exposure_mode = _read_str(data, "exposure_mode", camera.exposure_mode)
    camera.drc_strength = _read_str(data, "drc_strength", camera.drc_strength)
    camera.rotation = _read_int(data, "rotation", camera.rotation)
    camera.awb_mode = _read_str(data, "awb_mode", camera.awb_mode)
    camera.meter_mode = _read_str(data, "meter_mode", camera.meter_mode)


def _parse_preview_config(config: Config, data: Mapping[str, Any]) -> None:
    preview = config.preview
    preview.path = _read_str(data, "path", preview.path)
    preview.format = _read_str(data, "format", preview.format)
    preview.interval = _read_int(data, "interval", preview.interval)
    preview.send_to_external = _read_bool(
        data,
        "send_to_external",
        preview.send_to_external,
    )
    preview.url = _read_str(data, "url", preview.url)


def _parse_ftp_upload_config(ftp_config: FtpUploadConfig, data: Mapping[str, Any]) -> None:
    ftp_config.host = _read_str(data, "host", ftp_config.host)
    ftp_config.port = _read_int(data, "port", ftp_config.port)
    ftp_config.user = _read_str(data, "user", ftp_config.user)
    ftp_config.password = _read_str(data, "password", ftp_config.password)
    ftp_config.server_source = _read_str(data, "server_source", ftp_config.server_source)


def _parse_s3_config(s3_config: S3Config, data: Mapping[str, Any]) -> None:
    if "endpoint_url" in data:
        s3_config.endpoint_url = None if data["endpoint_url"] is None else str(data["endpoint_url"])
    s3_config.access_key = _read_str(data, "access_key", s3_config.access_key)
    s3_config.secret_key = _read_str(data, "secret_key", s3_config.secret_key)
    s3_config.bucket = _read_str(data, "bucket", s3_config.bucket)
    if "region" in data:
        s3_config.region = None if data["region"] is None else str(data["region"])


def _parse_server_upload_config(config: Config, data: Mapping[str, Any]) -> None:
    server_upload = config.server_upload
    server_upload.enable = _read_bool(data, "enable", server_upload.enable)
    server_upload.scheme = _read_str(data, "scheme", server_upload.scheme)

    upload_data = _get_section(data, "config")
    if server_upload.scheme == "ftp":
        ftp_config = FtpUploadConfig()
        _parse_ftp_upload_config(ftp_config, upload_data)
        server_upload.config = ftp_config
    else:
        s3_config = S3Config()
        _parse_s3_config(s3_config, upload_data)
        server_upload.config = s3_config


def _parse_video_config(config: Config, data: Mapping[str, Any]) -> None:
    video = config.video
    video.dir = _read_str(data, "dir", video.dir)
    video.format = _read_str(data, "format", video.format)
    video.resolution = _read_resolution(data, "resolution", video.resolution)

    encoder = _get_section(data, "encoder")
    video.h264_profile = _read_str(encoder, "profile", video.h264_profile)
    video.h264_level = _read_str(encoder, "level", video.h264_level)
    video.h264_bitrate = _read_int(encoder, "bitrate", video.h264_bitrate)
    video.h264_quality = _read_int(encoder, "quality", video.h264_quality)


def _parse_wifi_config(config: Config, data: Mapping[str, Any]) -> None:
    config.wifi.delay = _read_int(data, "delay", config.wifi.delay)


def _parse_hardware_config(config: Config, data: Mapping[str, Any]) -> None:
    hardware = config.hardware
    hardware.pcb_version = _read_str(data, "pcb_version", hardware.pcb_version)
    hardware.use_leds = _read_bool(data, "use_leds", hardware.use_leds)
    hardware.use_buttons = _read_bool(data, "use_buttons", hardware.use_buttons)
    hardware.use_adc = _read_bool(data, "use_adc", hardware.use_adc)


def _parse_msteams_config(config: Config, data: Mapping[str, Any]) -> None:
    msteams = config.msteams
    msteams.enable = _read_bool(data, "enable", msteams.enable)
    if "url" in data:
        msteams.url = None if data["url"] is None else str(data["url"])
    msteams.max_failed_send_attempts = _read_int(
        data,
        "max_failed_send_attempts",
        msteams.max_failed_send_attempts,
    )


def _parse_adc_config(config: Config, data: Mapping[str, Any]) -> None:
    adc = config.adc
    adc.threshold_external_power = _read_float(
        data,
        "threshold_external_power",
        adc.threshold_external_power,
    )
    adc.threshold_low_battery = _read_float(
        data,
        "threshold_low_battery",
        adc.threshold_low_battery,
    )


def _get_section(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Return a nested mapping or an empty mapping if the value is not a mapping."""
    return _as_section(data.get(key))


def _as_section(value: Any) -> Mapping[str, Any]:
    """Normalize a potential YAML section to a string-keyed mapping."""
    if isinstance(value, dict):
        return value
    return {}


def _read_bool(data: Mapping[str, Any], key: str, default: bool) -> bool:
    """Read a boolean-like config value."""
    return bool(data.get(key, default))


def _read_int(data: Mapping[str, Any], key: str, default: int) -> int:
    """Read an integer config value."""
    return int(data.get(key, default))


def _read_float(data: Mapping[str, Any], key: str, default: float) -> float:
    """Read a float config value."""
    return float(data.get(key, default))


def _read_str(data: Mapping[str, Any], key: str, default: str) -> str:
    """Read a string config value."""
    return str(data.get(key, default))


def _read_resolution(
    data: Mapping[str, Any],
    key: str,
    default: tuple[int, int],
) -> tuple[int, int]:
    """Read a resolution mapping with width and height."""
    raw_resolution = data.get(key)
    if not isinstance(raw_resolution, dict):
        return default
    width = int(raw_resolution.get("width", default[0]))
    height = int(raw_resolution.get("height", default[1]))
    return (width, height)


def _resolve_path(path: str) -> str:
    """Resolve a configured path to an absolute path."""
    return str(Path(path).expanduser().resolve())
