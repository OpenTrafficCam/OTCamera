"""OTCamera config variables.

All the configuration of OTCamera is done here.

"""
# Copyright (C) 2021 OpenTrafficCam Contributors
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


import socket
from pathlib import Path
from typing import Union

from OTCamera.html_updater import ConfigData, ConfigHtmlId

DEBUG_MODE_ON = True
"""Turn debug mode on to get additional log entries."""

START_HOUR = 6
"""Hour of day when to start recording."""
END_HOUR = 22
"""Hour of day when to end recording."""
INTERVAL_LENGTH = 15
"""Interval length in minutes before video splits."""
NUM_INTERVALS = 0
"""Number of full intervals to record (0=infinit)."""
PREVIEW_INTERVAL = 5
"""Interval between two preview images in seconds."""

MIN_FREE_SPACE = 1
"""free space in GB on sd card before old videos get deleted."""
PREFIX = socket.gethostname()
"""prefix for videoname and annotation."""
VIDEO_DIR = "~/videos/"
"""path to safe videofiles."""
PREVIEW_PATH = "~/OTCamera/webfiles/preview.jpg"
"""path to save preview."""
TEMPLATE_HTML_PATH = "~/OTCamera/webfiles/template.html"
"""Path to template HTML"""
INDEX_HTML_PATH = "~/OTCamera/webfiles/index.html"
"""Path to the auto generated index HTML."""
OFFLINE_HTML_PATH = "~/OTCamera/webfiles/offline.html"
"""Path to the HTML to be displayed when OTCamera is offline"""


# camera settings
FPS = 20
"""Frames per Second. 10-20 should be enough."""
RESOLUTION = (1640, 1232)
"""Resolution of the camera module works internally.
Field of view could be smaller with other values."""
EXPOSURE_MODE = "nightpreview"
"""Controls the analog and digital gains."""
DRC_STRENGTH = "high"
"""Sets dynamic range compression to lighten dark areas and to darken light areas."""
ROTATION = 180
"""Rotate the whole camera image."""
AWB_MODE = "greyworld"
"""Controls the auto white balancing mode. `greyworld`
is a specific mode for NoIR modules."""

# video settings
VIDEO_FORMAT = "h264"
"""Encoding format."""
PREVIEW_FORMAT = "jpeg"
"""Filetype of the static preview image."""
RESOLUTION_SAVED_VIDEO_FILE = (800, 600)
"""Resolution of the saved Videofile, not the camera itself."""
H264_PROFILE = "high"
"""Profile used in h264 encoder."""
H264_LEVEL = "4"
"""Level used in h264 encoder."""
H264_BITRATE = 600000
"""Bitrate used in h264 encoder."""
H264_QUALITY = 30
"""Quality used in h264 encoder."""

# hardware settings
USE_LED = False
"""True if Status-LEDs are connected."""
USE_BUTTONS = False
"""True if hardware buttons are connected."""
WIFI_DELAY = 900
"""Delay in seconds before wifi turns off."""


def read_user_config(path_to_config: Union[str, Path]) -> dict:
    validate_user_config()

    if not Path(path_to_config).is_file():
        # TODO: read default config
        pass


def validate_user_config():
    pass


def get_config_settings() -> ConfigData:
    """Returns OTCamera's configuration settings"""

    return ConfigData(
        debug_mode_on=(ConfigHtmlId.DEBUG_MODE_ON, DEBUG_MODE_ON),
        start_hour=(ConfigHtmlId.START_HOUR, START_HOUR),
        end_hour=(ConfigHtmlId.END_HOUR, END_HOUR),
        interval_video_split=(
            ConfigHtmlId.INTERVAL_VIDEO_SPLIT,
            INTERVAL_LENGTH,
        ),
        num_intervals=(ConfigHtmlId.NUM_INTERVALS, NUM_INTERVALS),
        preview_interval=(ConfigHtmlId.PREVIEW_INTERVAL, PREVIEW_INTERVAL),
        min_free_space=(ConfigHtmlId.MIN_FREE_SPACE, MIN_FREE_SPACE),
        prefix=(ConfigHtmlId.PREFIX, PREFIX),
        video_dir=(ConfigHtmlId.VIDEO_DIR, VIDEO_DIR),
        preview_path=(ConfigHtmlId.PREVIEW_PATH, PREVIEW_PATH),
        template_html_path=(ConfigHtmlId.TEMPLATE_HTML_PATH, TEMPLATE_HTML_PATH),
        index_html_path=(ConfigHtmlId.INDEX_HTML_PATH, INDEX_HTML_PATH),
        fps=(ConfigHtmlId.FPS, FPS),
        resolution=(ConfigHtmlId.RESOLUTION, RESOLUTION),
        exposure_mode=(ConfigHtmlId.EXPOSURE_MODE, EXPOSURE_MODE),
        drc_strength=(ConfigHtmlId.DRC_STRENGTH, DRC_STRENGTH),
        rotation=(ConfigHtmlId.ROTATION, ROTATION),
        awb_mode=(ConfigHtmlId.AWB_MODE, AWB_MODE),
        video_format=(ConfigHtmlId.VIDEO_FORMAT, VIDEO_FORMAT),
        preview_format=(ConfigHtmlId.PREVIEW_FORMAT, PREVIEW_FORMAT),
        res_of_saved_video_file=(
            ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE,
            RESOLUTION_SAVED_VIDEO_FILE,
        ),
        h264_profile=(ConfigHtmlId.H264_PROFILE, H264_PROFILE),
        h264_level=(ConfigHtmlId.H264_LEVEL, H264_LEVEL),
        h264_bitrate=(ConfigHtmlId.H264_BITRATE, H264_BITRATE),
        h264_quality=(ConfigHtmlId.H264_QUALITY, H264_QUALITY),
        use_led=(ConfigHtmlId.USE_LED, USE_LED),
        use_buttons=(ConfigHtmlId.USE_BUTTONS, USE_BUTTONS),
        wifi_delay=(ConfigHtmlId.WIFI_DELAY, WIFI_DELAY),
    )


VIDEO_DIR = str(Path(VIDEO_DIR).expanduser().resolve())
PREVIEW_PATH = str(Path(PREVIEW_PATH).expanduser().resolve())
TEMPLATE_HTML_PATH = str(Path(TEMPLATE_HTML_PATH).expanduser().resolve())
INDEX_HTML_PATH = str(Path(INDEX_HTML_PATH).expanduser().resolve())
OFFLINE_HTML_PATH = str(Path(OFFLINE_HTML_PATH).expanduser().resolve())
