from enum import Enum
from abc import ABC
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Tuple, Union

from bs4 import BeautifulSoup, Tag


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
    NUM_INTERVALS = "num-intervals"
    PREVIEW_INTERVAL = "preview-interval"
    MIN_FREE_SPACE = "min-free-space"
    PREFIX = "prefix"
    VIDEO_DIR = "video-dir"
    PREVIEW_PATH = "preview-path"
    FPS = "fps"
    RESOLUTION = "resolution"
    EXPOSURE_MODE = "exposure-mode"
    DRC_STRENGTH = "drc-strength"
    ROTATION = "rotation"
    AWB_MODE = "awb-mode"
    VIDEO_FORMAT = "video-format"
    PREVIEW_FORMAT = "preview-format"
    H264_PROFILE = "h264-profile"
    H264_BITRATE = "h264-bitrate"
    H264_QUALITY = "h264-quality"
    USE_LED = "use-led"
    USE_BUTTONS = "use-buttons"
    WIFI_DELAY = "wifi-delay"


@dataclass
class OTCameraHTMLDataObject(ABC):
    """Represents"""

    def get_properties(self) -> list[Tuple]:
        return [getattr(self, field.name) for field in fields(self)]


@dataclass
class StatusData(OTCameraHTMLDataObject):
    """Class containing OTCamera's status information."""

    time: Tuple[str, str]
    hostname: Tuple[str, str]
    free_diskspace: Tuple[str, int]
    num_videos_recorded: Tuple[str, int]
    currently_recording: Tuple[str, bool]
    wifi_active: Tuple[str, bool]
    low_battery: Tuple[str, bool]
    power_button_active: Tuple[str, bool]
    hour_button_active: Tuple[str, bool]
    wifi_ap_on: Tuple[str, bool]


@dataclass
class ConfigData(OTCameraHTMLDataObject):
    """Class representing OTCamera's current configuration file"""

    debug_mode_on: Tuple[str, bool]
    start_hour: Tuple[str, int]
    end_hour: Tuple[str, int]
    n_intervals: Tuple[str, int]
    preview_interval: Tuple[str, int]
    min_free_space: Tuple[str, int]
    prefix: Tuple[str, str]
    video_dir: Tuple[str, str]
    preview_path: Tuple[str, str]

    # Camera settings
    fps: Tuple[str, int]
    resolution: Tuple[str, Tuple[int, int]]
    exposure_mode: Tuple[str, str]
    drc_strength: Tuple[str, str]
    rotation: Tuple[str, int]
    awb_mode: Tuple[str, str]

    # Video settings
    video_format: Tuple[str, str]
    preview_format: Tuple[str, str]
    res_of_saved_video_file: Tuple[str, Tuple[int, int]]
    h264_profile: Tuple[str, str]
    h264_bitrate: Tuple[str, int]
    h264_quality: Tuple[str, int]

    # Hardware settings
    use_led: Tuple[str, bool]
    use_buttons: Tuple[str, bool]
    wifi_delay: Tuple[str, int]


class OTCameraHTMLUpdater:
    def __init__(
        self,
        status_info_id: str = "status-info",
        config_info_id: str = "config-info",
        debug_mode_on: bool = False,
    ) -> None:
        self.status_info_id = status_info_id
        self.config_info_id = config_info_id
        self.debug_mode_on = debug_mode_on

    def update_info(
        self,
        html_filepath: Union[str, Path],
        html_savepath: Union[str, Path],
        status_info: StatusData,
        config_info: ConfigData,
    ):
        html_tree = self._parse_html(Path(html_filepath))
        # Update status info
        self._update_by_id(html_tree, status_info)

        # Update config info
        if self.debug_mode_on:
            self._enable_tag_by_id(html_tree, self.config_info_id)
            self._update_by_id(html_tree, config_info)

        self._save(html_tree, Path(html_savepath))

    def disable_info(self, html_filepath: Union[str, Path]):
        html_tree = self._parse_html(html_filepath)
        self._disable_tag_by_id(html_tree, self.status_info_id)
        self._disable_tag_by_id(html_tree, self.config_info_id)
        # TODO: write to file
        self._save(html_tree, html_filepath)

    def _parse_html(self, html_filepath: Path) -> BeautifulSoup:
        with open(html_filepath) as html_stream:
            soup = BeautifulSoup(html_stream, "html.parser")
        return soup

    def _update_by_id(self, html_tree: Tag, update_info: OTCameraHTMLDataObject):
        for id, update_content in update_info.get_properties():
            self._change_content(html_tree.find(id=id), str(update_content))

    def _save(self, html_tree: Tag, save_path: Path):
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(str(html_tree))

    def _disable_tag_by_id(self, html_tag: Tag, id: str) -> None:
        id_tag = html_tag.find(id=id)
        if id_tag:
            id_tag["style"] = "display: none"

    def _enable_tag_by_id(self, html_tag: Tag, id: str) -> None:
        id_tag = html_tag.find(id=id)
        if id_tag:
            id_tag["style"] = "display: revert"

    def _change_content(self, html_tag: Tag, content: str) -> None:
        if html_tag:
            html_tag.string = content


def main(html_filepath: Path, html_savepath: Union[str, Path], status_data: StatusData):
    html_updater = OTCameraHTMLUpdater()
    html_updater.update_info(
        html_filepath, html_savepath, status_info=status_data, config_info=None
    )
    html_updater.disable_info(html_savepath)


if __name__ == "__main__":
    index_html_path = Path(__file__).parent / "webfiles/template.html"
    save_path = Path(__file__).parent / "webfiles/index.html"
    status_data = StatusData(
        time=("time", "2022-05-05T11:26:30"),
        hostname=("hostname", "my-hostname"),
        free_diskspace=("free-diskspace", 12),
        num_videos_recorded=("num-videos", 4),
        currently_recording=("currently-recording", True),
        wifi_active=("wifi-active", True),
        low_battery=("low-battery", False),
        power_button_active=("power-button-active", True),
        hour_button_active=("hour-button-active", False),
        wifi_ap_on=("wifi-ap-on", False),
    )
    main(index_html_path, save_path, status_data)
