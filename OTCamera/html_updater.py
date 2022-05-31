from abc import ABC
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Any, Tuple, Union

from bs4 import BeautifulSoup, Tag

from OTCamera.helpers import log


class StatusHtmlId(Enum):
    TIME = "time"
    HOSTNAME = "hostname"
    FREE_DISKSPACE = "free-diskspace"
    NUM_VIDEOS_RECORDED = "num-videos"
    CURRENTLY_RECORDING = "currently-recording"
    WIFI_ACTIVE = "wifi-active"
    LOW_BATTERY = "low-battery"
    POWER_BUTTON_ACTIVE = "power-button-active"
    HOUR_BUTTON_ACTIVE = "hour-button-active"
    WIFI_AP_ON = "wifi-ap-on"


class ConfigHtmlId(Enum):
    DEBUG_MODE_ON = "debug-mode-on"
    START_HOUR = "start-hour"
    END_HOUR = "end-hour"
    INTERVAL_VIDEO_SPLIT = "interval-video-split"
    NUM_INTERVALS = "num-intervals"
    PREVIEW_INTERVAL = "preview-interval"
    MIN_FREE_SPACE = "min-free-space"
    PREFIX = "prefix"
    VIDEO_DIR = "video-dir"
    PREVIEW_PATH = "preview-path"
    TEMPLATE_HTML_PATH = "template-html-path"
    INDEX_HTML_PATH = "index-html-path"
    FPS = "fps"
    RESOLUTION = "resolution"
    EXPOSURE_MODE = "exposure-mode"
    DRC_STRENGTH = "drc-strength"
    ROTATION = "rotation"
    AWB_MODE = "awb-mode"
    VIDEO_FORMAT = "video-format"
    PREVIEW_FORMAT = "preview-format"
    RESOLUTION_SAVED_VIDEO_FILE = "resolution-saved-video-file"
    H264_PROFILE = "h264-profile"
    H264_LEVEL = "h264-level"
    H264_BITRATE = "h264-bitrate"
    H264_QUALITY = "h264-quality"
    USE_LED = "use-led"
    USE_BUTTONS = "use-buttons"
    WIFI_DELAY = "wifi-delay"


class LogHtmlId(Enum):
    LOG_DATA = "log-data"


@dataclass
class OTCameraDataObject(ABC):
    """
    Represents OTCamera information to be displayed on the status website.

    All properties that inherit from `OTCameraDataObject` need to be a tuple of
    type Tuple[Enum, Any].
    The Enum represents the unique HTML id to be found in the HTML document.
    Thus the value of the Enum refers to an HTML id of a HTML tag.
    """

    def get_properties(self) -> list[Tuple[Enum, Any]]:
        """Returns all properties of this class as a list of tuples."""
        return [getattr(self, field.name) for field in fields(self)]


@dataclass
class StatusDataObject(OTCameraDataObject):
    """Status information to be displayed on the status website."""

    time: Tuple[Enum, str]
    hostname: Tuple[Enum, str]
    free_diskspace: Tuple[Enum, str]
    num_videos_recorded: Tuple[Enum, int]
    currently_recording: Tuple[Enum, bool]
    wifi_active: Tuple[Enum, bool]
    low_battery: Tuple[Enum, bool]
    power_button_active: Tuple[Enum, bool]
    hour_button_active: Tuple[Enum, bool]
    wifi_ap_on: Tuple[Enum, bool]


@dataclass
class ConfigDataObject(OTCameraDataObject):
    """Configuration information to be displayed on the status website"""

    debug_mode_on: Tuple[Enum, bool]
    start_hour: Tuple[Enum, int]
    end_hour: Tuple[Enum, int]
    interval_video_split: Tuple[Enum, int]
    num_intervals: Tuple[Enum, int]
    preview_interval: Tuple[Enum, int]
    min_free_space: Tuple[Enum, int]
    prefix: Tuple[Enum, str]
    video_dir: Tuple[Enum, str]
    preview_path: Tuple[Enum, str]
    template_html_path: Tuple[Enum, str]
    index_html_path: Tuple[Enum, str]

    # Camera settings
    fps: Tuple[Enum, int]
    resolution: Tuple[Enum, Tuple[int, int]]
    exposure_mode: Tuple[Enum, str]
    drc_strength: Tuple[Enum, str]
    rotation: Tuple[Enum, int]
    awb_mode: Tuple[Enum, str]

    # Video settings
    video_format: Tuple[Enum, str]
    preview_format: Tuple[Enum, str]
    res_of_saved_video_file: Tuple[Enum, Tuple[int, int]]
    h264_profile: Tuple[Enum, str]
    h264_bitrate: Tuple[Enum, int]
    h264_level: Tuple[Enum, str]
    h264_quality: Tuple[Enum, int]

    # Hardware settings
    use_led: Tuple[Enum, bool]
    use_buttons: Tuple[Enum, bool]
    wifi_delay: Tuple[Enum, int]


@dataclass
class LogDataObject(OTCameraDataObject):
    """Log information to be displayed on the status website"""

    log_data: Tuple[Enum, str]


class OTCameraHTMLUpdater:
    def __init__(
        self,
        status_info_id: str = "status-info",
        config_info_id: str = "config-info",
        log_info_id: str = "log-info",
        debug_mode_on: bool = False,
    ) -> None:
        self.status_info_id = status_info_id
        self.config_info_id = config_info_id
        self.log_info_id = log_info_id
        self.debug_mode_on = debug_mode_on

    def update_info(
        self,
        html_filepath: Union[str, Path],
        html_savepath: Union[str, Path],
        status_info: OTCameraDataObject,
        config_info: OTCameraDataObject,
        log_info: OTCameraDataObject,
    ):
        html_tree = self._parse_html(Path(html_filepath))
        # Update status info
        self._enable_tag_by_id(html_tree, self.status_info_id)
        self._update_by_id(html_tree, status_info)

        # Update config info
        if self.debug_mode_on:
            self._enable_tag_by_id(html_tree, self.config_info_id)
            self._update_by_id(html_tree, config_info)

        # Update log info
        if self.debug_mode_on:
            self._enable_tag_by_id(html_tree, self.log_info_id)
            self._update_by_id(html_tree, log_info)

        self._save(html_tree, Path(html_savepath))
        log.write("index.html status information updated", log.LogLevel.DEBUG)

    def disable_info(self, html_filepath: Union[str, Path]):
        html_tree = self._parse_html(html_filepath)
        self._disable_tag_by_id(html_tree, self.status_info_id)
        self._disable_tag_by_id(html_tree, self.config_info_id)
        self._save(html_tree, html_filepath)

    def display_offline_info(
        self,
        offline_html_path: Union[str, Path],
        html_save_path: Union[str, Path],
        log_info: LogDataObject,
    ):
        html_tree = self._parse_html(offline_html_path)
        if self.debug_mode_on:
            self._enable_tag_by_id(html_tree, self.log_info_id)
            self._update_by_id(html_tree, log_info)
        self._save(html_tree, html_save_path)

    def _parse_html(self, html_filepath: Path) -> BeautifulSoup:
        with open(html_filepath) as html_stream:
            soup = BeautifulSoup(html_stream, "html.parser")
        return soup

    def _update_by_id(self, html_tree: Tag, update_info: OTCameraDataObject):
        for id, update_content in update_info.get_properties():
            self._change_content(html_tree.find(id=id.value), str(update_content))

    def _save(self, html_tree: Tag, save_path: Path):
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(str(html_tree))

    def _disable_tag_by_id(self, html_tag: Tag, id: str) -> None:
        id_tag = html_tag.find(id=id)
        if id_tag:
            id_tag["style"] = "display: none"

    def _enable_tag_by_id(self, html_tag: Tag, id: str) -> None:
        """Make a BeautifulSoup tag visible by reading"""
        id_tag = html_tag.find(id=id)
        if id_tag:
            id_tag["style"] = "display: revert"

    def _change_content(self, html_tag: Tag, content: str) -> None:
        """Change content of an BeautifulSoup tag."""
        if html_tag:
            html_tag.string = content
