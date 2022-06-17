import copy
from abc import ABC
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Any, Tuple, Union

from bs4 import BeautifulSoup, Tag

from OTCamera.helpers import log


class StatusHtmlId(Enum):
    """Enum representing status settings as HTML id on the status website.

    An enum member's values represent the actual HTML IDs used in the status website.
    """

    TIME = "time"
    HOSTNAME = "hostname"
    FREE_DISKSPACE = "free-diskspace"
    NUM_VIDEOS_RECORDED = "num-videos"
    CURRENTLY_RECORDING = "currently-recording"
    WIFI_ACTIVE = "wifi-active"
    LOW_BATTERY = "low-battery"
    POWER_BUTTON_ACTIVE = "power-button-active"
    HOUR_BUTTON_ACTIVE = "24-7-recording"
    WIFI_AP_ON = "wifi-ap-on"


class ConfigHtmlId(Enum):
    """Enum representing config settings as HTML id on the status website.

    An enum member's values represent the actual HTML IDs used in the status website.
    """

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
    """Enum representing log variables as HTML id on the status website.

    An enum member's values represent the actual HTML IDs used in the status website.
    """

    LOG_DATA = "log-data"


@dataclass
class OTCameraDataObject(ABC):
    """Abstract data class representing information to be displayed on the status website.

    All properties that inherit from `OTCameraDataObject` need to be a tuple of
    type Tuple[Enum, Any].
    The Enum represents the unique HTML id to be found in the HTML document.
    Thus the value of the `Enum` refers to an HTML id of a HTML tag.
    """

    def get_properties(self) -> list[Tuple[Enum, Any]]:
        """Returns all properties of this class as a list of tuples.

        Returns:
            list[Tuple[Enum, Any]]: The properties of the concrete class.
        """
        return [getattr(self, field.name) for field in fields(self)]


@dataclass
class StatusDataObject(OTCameraDataObject):
    """Status information to be displayed on the status website.

    This class inherits from OTCameraDataObject and its properties need to be a tuple of
    type Tuple[StatusHtmlId, Any] where `StatusHtmnlId` is an `Enum`.
    StatusHtmlId represents the unique HTML id to be found in the HTML document.
    Thus the value of an`Enum` member refers to an HTML id of a HTML tag.
    """

    free_diskspace: Tuple[StatusHtmlId, str]
    num_videos_recorded: Tuple[StatusHtmlId, int]
    currently_recording: Tuple[StatusHtmlId, bool]
    low_battery: Tuple[StatusHtmlId, bool]
    hour_button_active: Tuple[StatusHtmlId, bool]


@dataclass
class ConfigDataObject(OTCameraDataObject):
    """Configuration information to be displayed on the status website

    This class inherits from OTCameraDataObject and its properties need to be a tuple of
    type Tuple[ConfigHtmlId, Any] where `ConfigHtmlId` is an `Enum`.
    StatusHtmlId represents the unique HTML id to be found in the HTML document.
    Thus the value of an`Enum` member refers to an HTML id of a HTML tag.
    """

    debug_mode_on: Tuple[ConfigHtmlId, bool]
    start_hour: Tuple[ConfigHtmlId, int]
    end_hour: Tuple[ConfigHtmlId, int]
    interval_video_split: Tuple[ConfigHtmlId, int]
    num_intervals: Tuple[ConfigHtmlId, int]
    preview_interval: Tuple[ConfigHtmlId, int]
    min_free_space: Tuple[ConfigHtmlId, int]
    prefix: Tuple[ConfigHtmlId, str]
    video_dir: Tuple[ConfigHtmlId, str]
    preview_path: Tuple[ConfigHtmlId, str]
    template_html_path: Tuple[ConfigHtmlId, str]
    index_html_path: Tuple[ConfigHtmlId, str]

    # Camera settings
    fps: Tuple[ConfigHtmlId, int]
    resolution: Tuple[ConfigHtmlId, Tuple[int, int]]
    exposure_mode: Tuple[ConfigHtmlId, str]
    drc_strength: Tuple[ConfigHtmlId, str]
    rotation: Tuple[ConfigHtmlId, int]
    awb_mode: Tuple[ConfigHtmlId, str]

    # Video settings
    video_format: Tuple[ConfigHtmlId, str]
    preview_format: Tuple[ConfigHtmlId, str]
    res_of_saved_video_file: Tuple[ConfigHtmlId, Tuple[int, int]]
    h264_profile: Tuple[ConfigHtmlId, str]
    h264_bitrate: Tuple[ConfigHtmlId, int]
    h264_level: Tuple[ConfigHtmlId, str]
    h264_quality: Tuple[ConfigHtmlId, int]

    # Hardware settings
    use_led: Tuple[ConfigHtmlId, bool]
    use_buttons: Tuple[ConfigHtmlId, bool]
    wifi_delay: Tuple[ConfigHtmlId, int]


@dataclass
class LogDataObject(OTCameraDataObject):
    """Log information to be displayed on the status website

    This class inherits from OTCameraDataObject and its properties need to be a tuple of
    type Tuple[LogHtmlId, Any] where `LogHtmlId`is an `Enum`.
    StatusHtmlId represents the unique HTML id to be found in the HTML document.
    Thus the value of an`Enum` member refers to an HTML id of a HTML tag.
    """

    log_data: Tuple[LogHtmlId, str]


STATUS_DESC: dict[StatusHtmlId, str] = {
    StatusHtmlId.FREE_DISKSPACE: "Free Disk Space",
    StatusHtmlId.NUM_VIDEOS_RECORDED: "Videos recorded",
    StatusHtmlId.CURRENTLY_RECORDING: "Camera Currently Recording",
    StatusHtmlId.LOW_BATTERY: "Battery Low",
    StatusHtmlId.HOUR_BUTTON_ACTIVE: "24/7 Recording",
}
"""Dict that contains the descriptions of values to be displayed on the status website.

The dictionary keys are of type `StatusHtmlId` which itself is an `Enum` representing
HTML id on the status website.
The keys values are their respective descriptions belonging to the HTML ids.

Returns:
    dict (StatusHmtlId, str): the mapping in form of a dictionary.
"""


CONFIG_DESC = {
    ConfigHtmlId.DEBUG_MODE_ON: "Debug Mode On",
    ConfigHtmlId.START_HOUR: "Start Hour",
    ConfigHtmlId.END_HOUR: "End Hour",
    ConfigHtmlId.INTERVAL_VIDEO_SPLIT: "Interval Length[min] Before Video Splits",
    ConfigHtmlId.NUM_INTERVALS: "Number of Full Intervals to Record",
    ConfigHtmlId.PREVIEW_INTERVAL: "Preview Interval",
    ConfigHtmlId.MIN_FREE_SPACE: "Minimum Free Space",
    ConfigHtmlId.PREFIX: "Prefix",
    ConfigHtmlId.VIDEO_DIR: "Video Directory",
    ConfigHtmlId.PREVIEW_PATH: "Preview Image Path",
    ConfigHtmlId.TEMPLATE_HTML_PATH: "Template HTML Path",
    ConfigHtmlId.INDEX_HTML_PATH: "Index HTML Path",
    ConfigHtmlId.FPS: "FPS",
    ConfigHtmlId.RESOLUTION: "Resolution",
    ConfigHtmlId.EXPOSURE_MODE: "Exposure Mode",
    ConfigHtmlId.DRC_STRENGTH: "DRC Strength",
    ConfigHtmlId.ROTATION: "Rotation",
    ConfigHtmlId.AWB_MODE: "AWB Mode",
    ConfigHtmlId.VIDEO_FORMAT: "Video Format",
    ConfigHtmlId.PREVIEW_FORMAT: "Preview Format",
    ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE: "Resolution of Saved Video File",
    ConfigHtmlId.H264_PROFILE: "H264 Profile",
    ConfigHtmlId.H264_LEVEL: "H264 Level",
    ConfigHtmlId.H264_BITRATE: "H264 Bitrate",
    ConfigHtmlId.H264_QUALITY: "H264 Quality",
    ConfigHtmlId.USE_LED: "Use LED",
    ConfigHtmlId.USE_BUTTONS: "Use Buttons",
    ConfigHtmlId.WIFI_DELAY: "Wi-Fi Delay",
}
"""Dict that contains the descriptions of values to be displayed on the status website.

The dictionary keys are of type `ConfigHtmlId` which itself is an `Enum` representin
HTML id on the status website.
The keys values are their respective descriptions belonging to the HTML ids.

Returns:
    dict (ConfigHtmlId, str): the mapping in form of a dictionary.
"""


class StatusWebsiteUpdater:
    """This class provides methods to change the contents of the status website's HTML.

    Attributes:
        html_path (Union[str, Path]): Path to the status website's HTML file.
        offline_html_path (Union[str, Path]): Path to the HTML file to be displayed
        when OTCamera is offline.
        html_save_path (Union[str, Path]): Path to save the updated HTML file.
        status_info_id (str, optional): The HTML id's tag corresponding to the
        status website's status info section. Defaults to "status-info".
        config_info_id (str, optional): The HTML id's tag corresponding to the
        status website's config info section. Defaults to "config-info".
        log_info_id (str, optional): The HTML id's tag corresponding to the status
        website's log info section. Defaults to "log-info".
        status_table_id (str, optional): The HTML id's tag corresponding to the
        status website's status HTML table. Defaults to "status-info-table".
        config_table_id (str, optional): The HTML id's tag corresponding to the
        status website's config HTML table. Defaults to "config-info-table".
        debug_mode_on (bool, optional): True if debug mode is enabled. Defaults to
        False.
    """

    def __init__(
        self,
        html_path: Union[str, Path],
        offline_html_path: Union[str, Path],
        html_save_path: Union[str, Path],
        status_info_id: str = "status-info",
        config_info_id: str = "config-info",
        log_info_id: str = "log-info",
        status_table_id: str = "status-info-table",
        config_table_id: str = "config-info-table",
        debug_mode_on: bool = False,
    ) -> None:
        self._html_data = self._parse_html(html_path)
        self._offline_html_data = self._parse_html(offline_html_path)
        self.html_save_path = html_save_path
        self.status_info_id = status_info_id
        self.config_info_id = config_info_id
        self.log_info_id = log_info_id
        self.status_table_id = status_table_id
        self.config_table_id = config_table_id
        self.debug_mode_on = debug_mode_on

    def update_info(
        self,
        status_info: OTCameraDataObject,
        config_info: OTCameraDataObject,
    ):
        """Updates the information on the status website.

        The config settings are only displayed when `debug_mode_on = True`.

        Args:
            status_info (OTCameraDataObject): The status information to be upated.
            config_info (OTCameraDataObject): The config settings to be updated.
        """
        html_tree = copy.copy(self._html_data)
        # Update status info
        self._enable_tag_by_id(html_tree, self.status_info_id)
        self._build_data_html_table(
            soup=html_tree,
            table_id=self.status_table_id,
            value_desc=STATUS_DESC,
            data=status_info,
        )
        # Update config info
        if self.debug_mode_on:
            self._enable_tag_by_id(html_tree, self.config_info_id)
            self._build_data_html_table(
                soup=html_tree,
                table_id=self.config_table_id,
                value_desc=CONFIG_DESC,
                data=config_info,
            )

        self._save(html_tree)
        log.write("index.html status information updated", log.LogLevel.DEBUG)

    def _build_data_html_table(
        self,
        soup: BeautifulSoup,
        table_id: str,
        value_desc: dict,
        data: OTCameraDataObject,
    ):
        """Builds a HTML data table and updates a HTML tag's content specified by `table_id`.

        Args:
            soup (BeautifulSoup): The status website's HTML tree represented by
            a BeautifulSoup object.
            table_id (str): The HTML id refering to the table in the HTML.
            value_desc (dict):  Dict containing all descriptions of all properties of
            `data`.
            data (OTCameraDataObject): The data to be inserted into the table.
        """
        table_tag = soup.find(id=table_id)
        for id, table_content in data.get_properties():
            table_row = soup.new_tag("tr", attrs={"id": id.value})
            table_tag.append(table_row)
            td_status_desc = soup.new_tag("td")
            td_status_val = soup.new_tag("td")
            self._change_content(td_status_desc, value_desc[id])
            self._change_content(td_status_val, str(table_content))

            table_row.append(td_status_desc)
            table_row.append(td_status_val)

    def disable_info(self):
        """Disables status website information making them invisible."""
        html_tree = copy.copy(self._html_data)
        self._disable_tag_by_id(html_tree, self.status_info_id)
        self._disable_tag_by_id(html_tree, self.config_info_id)
        self._save(html_tree)

    def display_offline_info(
        self,
        log_info: LogDataObject,
    ):
        """Displays offline content in the HTML.

        Args:
            log_info (LogDataObject): The log data to be displayed in the HTML file.
        """
        log.write("Display offline html", log.LogLevel.DEBUG)
        html_tree = copy.copy(self._offline_html_data)
        if self.debug_mode_on:
            self._enable_tag_by_id(html_tree, self.log_info_id)
            self._update_by_id(html_tree, log_info)
        else:
            self._disable_tag_by_id(html_tree, self.log_info_id)
        self._save(html_tree)

    def _parse_html(self, html_filepath: Path) -> BeautifulSoup:
        """Parses a HTML file as a `BeautifulSoup` object.

        Args:
            html_filepath (Path): The HTML file to be parsed.

        Returns:
            BeautifulSoup: Represents the HTML parse tree.
        """
        with open(html_filepath) as html_stream:
            soup = BeautifulSoup(html_stream, "html.parser")
        return soup

    def _update_by_id(self, html_tree: Tag, update_info: OTCameraDataObject):
        """Uses parameter `update_info` to update the contents of the tags
        specified in `update_info`.

        Args:
            html_tree (Tag): _description_
            update_info (OTCameraDataObject): _description_
        """
        for id, update_content in update_info.get_properties():
            self._change_content(html_tree.find(id=id.value), str(update_content))

    def _save(self, html_tree: Tag):
        """Save the html tree to a file specified by `self.html_save_path`.

        Args:
            html_tree (Tag): The HTML to be saved.
        """
        with open(self.html_save_path, "w", encoding="utf-8") as f:
            f.write(str(html_tree))

    def _disable_tag_by_id(self, html_tag: Tag, id: str) -> None:
        """Disable a HTML tag by its id.

        Args:
            html_tag (Tag): The html containing the id.
            id (str): The HTML id referring to the tag to be disabled.
        """
        id_tag = html_tag.find(id=id)
        if id_tag:
            id_tag["style"] = "display: none"

    def _enable_tag_by_id(self, html_tag: Tag, id: str) -> None:
        """Enable a HTML tag by its id.

        Args:
            html_tag (Tag): HTML tag to be enabled.
            id (str): The HTML id referring to the tag to be enabled.
        """
        id_tag = html_tag.find(id=id)
        if id_tag:
            id_tag["style"] = "display: revert"

    def _change_content(self, html_tag: Tag, content: str) -> None:
        """Change content of an HTML tag.

        Args:
            html_tag (Tag): The HTML tag containing the content to be changed.
            content (str): The content to be changed.
        """
        if html_tag:
            html_tag.string = content
