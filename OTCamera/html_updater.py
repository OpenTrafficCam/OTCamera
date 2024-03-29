"""The `html_updater` module serves the purpose of creating and updating the HTML to be
displayed on the OTCamera Status Website.

Classes:
    - StatusWebsiteUpdater
    - OTCameraDataObject
    - StatusDataObject
    - ConfigDataObject
    - LogDataObject

Enums:
    - StatusHtmlId
    - ConfigHtmlId
    - LogHtmlId
    - BannerHtmlId

Variables:
    - STATUS_DESC
    - CONFIG_DESC
    - BANNER_DESC

"""
# Copyright (C) 2023 OpenTrafficCam Contributors
# <https://github.com/OpenTrafficCam>
# <team@opentrafficcam.org>

# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A

# PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program.  If not, see <https://www.gnu.org/licenses/>.

import copy
from abc import ABC
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Any, Tuple, Union

from bs4 import BeautifulSoup, Tag

from OTCamera.helpers import log


class StatusHtmlId(Enum):
    """Enum that represents OTCamera status variables' HTML ids to be used in the
    OTCamera status website's HTML.
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
    EXT_POWER_SUPPLY_CONNECTED = "ext-power-supply-connected"
    MS_TEAMS_WEBHOOK_ENABLED = "ms-teams-webhook-enabled"
    TIME_UNTIL_WIFI_OFF = "time-until-wifi-off"


class ConfigHtmlId(Enum):
    """Enum that represents OTCamera config variables' HTML ids to be used in the
    OTCamera status website's HTML.
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
    """Enum representing the HTML id of the OTCamera log data to be used in the
    OTCamera status website's HTML.
    """

    LOG_DATA = "log-data"


class BannerHtmlId(Enum):
    """Enum that represents the OTCamera status websites' banner HTML ids."""

    RECORDING_BANNER = "recording-banner"
    EXT_POWER_SUPPLY_BANNER = "ext-power-supply-banner"


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

    free_diskspace: Tuple[Enum, str]
    num_videos_recorded: Tuple[Enum, int]
    currently_recording: Tuple[Enum, bool]
    low_battery: Tuple[Enum, bool]
    hour_button_active: Tuple[Enum, bool]
    external_power_supply_connected: Tuple[Enum, bool]
    ms_teams_webhook_enabled: Tuple[Enum, bool]
    time_until_wifi_off: Tuple[Enum, str]


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


STATUS_DESC = {
    StatusHtmlId.FREE_DISKSPACE: "Free Disk Space",
    StatusHtmlId.NUM_VIDEOS_RECORDED: "Videos recorded",
    StatusHtmlId.CURRENTLY_RECORDING: "Camera Currently Recording",
    StatusHtmlId.LOW_BATTERY: "Battery Low",
    StatusHtmlId.HOUR_BUTTON_ACTIVE: "24/7 Recording",
    StatusHtmlId.EXT_POWER_SUPPLY_CONNECTED: "External Power Supply Connected",
    StatusHtmlId.MS_TEAMS_WEBHOOK_ENABLED: "MS Teams Webhook Enabled",
    StatusHtmlId.TIME_UNTIL_WIFI_OFF: "Turn Wi-Fi Off In",
}
"""Dictionary that maps a StatusHtmlId to its description to be displayed on the status
website.

Dictionary of type dict[StatusHtmlId, str].
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
"""Dictionary that maps a `ConfigHtmlId` to its description to be displayed on the
status website.

Dictionary of type dict[ConfigHtmlId, str].
"""

BANNER_DESC = {
    "BANNER_RECORDING": "Currently recording",
    "BANNER_NOT_RECORDING": "Not recording",
    "BANNER_NOT_ALWAYS_RECORDING": "Currently recording (not 24/7)",
    "BANNER_EXT_POWER_SUPPLY_NOT_CONNECTED": "Not connected to external power supply",
}


@dataclass
class LogDataObject(OTCameraDataObject):
    """Log information to be displayed on the status website"""

    log_data: Tuple[Enum, str]


class StatusWebsiteUpdater:
    """This class is responsible for the generation of the HTML to be displayed on the
    OTCamera status website.

    The class requires a template HTML file with the following contents:

    ```html
    <!DOCTYPE html>

    <html>

    <head>
        <meta charset="utf-8" />
        <meta content="width=device-width, initial-scale=1" name="viewport"/>
        <meta content="5" http-equiv="refresh" />
        <meta content="no-cache, no-store, must-revalidate" http-equiv="Cache-Control"/>
        <meta content="no-cache" http-equiv="Pragma" />
        <meta content="0" http-equiv="Expires" />
        <!-- Bootstrap CSS -->
        <link href="css/bootstrap.min.css" rel="stylesheet"/>
        <title>OTCamera</title>
    </head>

    <body>
        <div class="container-fluid" id="recording-banner"></div>
        <div class="container-fluid" id="ext-power-supply-banner"></div>
        <div class="container-fluid ">
            <img class="img-fluid gy-5" alt="Vorschau" src="preview.jpg"/>
        </div>
        <br>
        <div class="container-fluid" id="status-info" style="display: none">
            <table class="table table-bordered" id="status-info-table">
                <tr>
                    <th>Status</th>
                    <th>Value</th>
                </tr>
            </table>
        </div>
        <div class="container-fluid" id="config-info" style="display: none">
            <table class="table table-bordered" id="config-info-table">
                <tr>
                    <th>Config Variable</th>
                    <th>Value</th>
                </tr>
            </table>
        </div>
    </body>

    </html>
    ```

    Args:
        template_html_path (Union[str, Path]): The status websites template HTML file.
        offline_html_path (Union[str, Path]): The status websites offline HTML file.
        html_save_path (Union[str, Path]): The actual HTML file that is served on a
        webserver. I.e. the index.html.
        status_info_id (str, optional): The HTML div id to hold the status information.
        Defaults to "status-info".
        config_info_id (str, optional): The HTML div id to hold the config information.
        Defaults to "config-info".
        log_info_id (str, optional): The HTML div id to hold the log information.
        Defaults to "log-info".
        status_table_id (str, optional): The HTML table id to hold all status variables.
        Defaults to "status-info-table".
        config_table_id (str, optional): The HTML table id to hold all config variables.
        Defaults to "config-info-table".
        debug_mode_on (bool, optional): Will display the config data if `True`.
        Defaults to False.
    """

    def __init__(
        self,
        template_html_path: Union[str, Path],
        offline_html_path: Union[str, Path],
        html_save_path: Union[str, Path],
        status_info_id: str = "status-info",
        config_info_id: str = "config-info",
        log_info_id: str = "log-info",
        status_table_id: str = "status-info-table",
        config_table_id: str = "config-info-table",
        debug_mode_on: bool = False,
    ) -> None:
        self._html_data = self._parse_html(template_html_path)
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
        currently_recording: bool,
        always_recording: bool,
        external_power_supply_connected: bool,
    ):
        """Updates the information of the status website.

        Args:
            status_info (OTCameraDataObject): Dataclass containing all status
            information required.
            config_info (OTCameraDataObject): Dataclass containing all config
            information.
            currently_recording (bool): Will display the either 'always recording' or
            the 'not always recording' banner depending on value of `always_recording`
            if `True`. Otherwise will display the 'not recording' banner.
            always_recording (bool): If `True` and `currently_recording=True` the
            'always recording' will be displayed.
            If `False` and `currently_recording=True` the **not always recording'
            banner will be displayed.
            external_power_supply_connected (bool): Will display the 'external power
            supply connected' banner if `True`.
        """
        html_tree = copy.copy(self._html_data)

        # Update record status banner
        self._set_record_status_banner(html_tree, currently_recording, always_recording)

        # Update external power supply banner
        self._set_external_power_supply_status_banner(
            html_tree, external_power_supply_connected
        )

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
            self._update_by_id(html_tree, config_info)
            self._build_data_html_table(
                soup=html_tree,
                table_id=self.config_table_id,
                value_desc=CONFIG_DESC,
                data=config_info,
            )

        self._save(html_tree)
        log.write("index.html status information updated", log.LogLevel.DEBUG)

    def _set_record_status_banner(
        self, soup: BeautifulSoup, currently_recording: bool, always_recording: bool
    ):
        """Sets a banner reflecting the current recording status of OTCamera

        A green banner indicates that OTCamera is currently recording.
        A yellow banner indicates that OTCamera is currently recording but not 24/7.
        A red banner indicates that OTCamera is not recording.

        Args:
            soup (BeautifulSoup): Represents the root of html tree.
            currently_recording(bool): Wether OTCamera is currently recording.
            always_recording(bool): Wether OTCamera is set to always record without
            breaks.
        """
        banner_section_tag = soup.find(id=BannerHtmlId.RECORDING_BANNER.value)
        if currently_recording:
            if always_recording:
                banner_tag = self._build_tag(
                    soup=soup,
                    tag_type="div",
                    class_attr="alert alert-success",
                    content=BANNER_DESC["BANNER_RECORDING"],
                )
            else:
                banner_tag = self._build_tag(
                    soup=soup,
                    tag_type="div",
                    class_attr="alert alert-warning",
                    content=BANNER_DESC["BANNER_NOT_ALWAYS_RECORDING"],
                )
        else:
            banner_tag = self._build_tag(
                soup=soup,
                tag_type="div",
                class_attr="alert alert-danger",
                content=BANNER_DESC["BANNER_NOT_RECORDING"],
            )
        banner_section_tag.append(banner_tag)

    def _set_external_power_supply_status_banner(
        self,
        soup: BeautifulSoup,
        external_power_supply_connected: bool,
    ):
        """View banner on status website informing about whether OTCamera is connected
        to an external power supply

        A red banner indicates that no external power supply is connected.

        Args:
            soup (BeautifulSoup): Represents the root of html tree.
            external_power_supply_connected(bool): If connected to external power
            supply.
        """
        banner_section_tag = soup.find(id=BannerHtmlId.EXT_POWER_SUPPLY_BANNER.value)
        if not external_power_supply_connected:
            banner_tag = self._build_tag(
                soup=soup,
                tag_type="div",
                class_attr="alert alert-danger",
                content=BANNER_DESC["BANNER_EXT_POWER_SUPPLY_NOT_CONNECTED"],
            )
            banner_section_tag.append(banner_tag)

    def _build_tag(
        self, soup: BeautifulSoup, tag_type: str, class_attr: str, content: str
    ) -> Tag:
        """Builds a new HTML tag with predefined class attributes and content"""
        tag = soup.new_tag(tag_type, attrs={"class": class_attr})
        self._change_content(tag, content)
        return tag

    def _build_data_html_table(
        self,
        soup: BeautifulSoup,
        table_id: str,
        value_desc: dict,
        data: OTCameraDataObject,
    ):
        """Builds a data table with the data passed to it.

        Args:
            soup (BeautifulSoup): Represents the root of html tree.
            table_id (str): The data table HTML id to append the generated table data
            to.
            value_desc (dict): Dictionary containing all descriptions for all fields
            defined in `OTCameraDataObject`. The key needs to be of type `Enum`
            (See `StatusHtmlId` class) representing the HTML id to access the
            description.
            data (OTCameraDataObject): Encapsulates OTCamera data information.
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
        """Disables the status and config info making it invisible
        on the status website.
        """
        html_tree = copy.copy(self._html_data)
        self._disable_tag_by_id(html_tree, self.status_info_id)
        self._disable_tag_by_id(html_tree, self.config_info_id)
        self._save(html_tree)

    def display_offline_info(
        self,
        log_info: LogDataObject,
    ):
        """Displays OTCamera offline page on the status website.

        Args:
            log_info (LogDataObject): The log data to be displayed on
            the status website.
        """
        html_tree = copy.copy(self._offline_html_data)
        if self.debug_mode_on:
            self._enable_tag_by_id(html_tree, self.log_info_id)
            self._update_by_id(html_tree, log_info)
        else:
            self._disable_tag_by_id(html_tree, self.log_info_id)
        self._save(html_tree)

    def _parse_html(self, html_filepath: Path) -> BeautifulSoup:
        """Parses an html file and returns BeautifulSoup object."""
        with open(html_filepath) as html_stream:
            soup = BeautifulSoup(html_stream, "html.parser")
        return soup

    def _update_by_id(self, html_tree: Tag, update_info: OTCameraDataObject):
        """Updates the the contents defined by the HTML ids contained in `update_info`.

        Args:
            html_tree (Tag): The html tree to updated.
            update_info (OTCameraDataObject): The information to be used for the update.
        """
        for id, update_content in update_info.get_properties():
            self._change_content(html_tree.find(id=id.value), str(update_content))

    def _save(self, html_tree: Tag):
        """Saves the HTML to path defined by `self.html_save_path`."""
        with open(self.html_save_path, "w", encoding="utf-8") as f:
            f.write(str(html_tree))

    def _disable_tag_by_id(self, html_tag: Tag, id: str) -> None:
        """Disables a tag by id making it invisible."""
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
