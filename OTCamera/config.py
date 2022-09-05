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

DEBUG_MODE_ON = True
"""Turn debug mode on to get additional log entries."""
USE_RELAY = False
"""Enable to start and stop sshrelay.service (need's to be configured)"""

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
NUM_LOG_FILES_HTML = 2
"""Number of log files to be displayed on the status website"""


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
METER_MODE = "average"
"""Retrieves or sets the metering mode of the camera. Possible values: ['average', 'spot', 'backlit', 'matrix']"""

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


VIDEO_DIR = str(Path(VIDEO_DIR).expanduser().resolve())
PREVIEW_PATH = str(Path(PREVIEW_PATH).expanduser().resolve())
TEMPLATE_HTML_PATH = str(Path(TEMPLATE_HTML_PATH).expanduser().resolve())
INDEX_HTML_PATH = str(Path(INDEX_HTML_PATH).expanduser().resolve())
OFFLINE_HTML_PATH = str(Path(OFFLINE_HTML_PATH).expanduser().resolve())
