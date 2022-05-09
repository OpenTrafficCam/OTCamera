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

DEBUG = True
"""Turn debug mode on to get additional log entries."""

STARTHOUR = 6
"""Hour of day when to start recording."""
ENDHOUR = 22
"""Hour of day when to end recording."""
INTERVAL = 15
"""Interval length in minutes before video splits."""
N_INTERVALS = 0
"""Number of full intervals to record (0=infinit)."""
PREVIEW_INTERVAL = 5
"""Interval between two preview images in seconds."""

MINFREESPACE = 1
"""free space in GB on sd card before old videos get deleted."""
PREFIX = socket.gethostname()
"""prefix for videoname and annotation."""
VIDEO_DIR = "~/videos/"
"""path to safe videofiles."""
PREVIEWPATH = "~/OTCamera/webfiles/preview.jpg"
"""path to save preview."""
TEMPLATE_HTML_PATH = "~/OTCamera/webfiles/template.html"
INDEX_HTML_PATH = "~/OTCamera/webfiles/index.html"


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
FORMAT = "h264"
"""Encoding format."""
PREVIEWFORMAT = "jpeg"
"""Filetype of the static preview image."""
RESIZE = (800, 600)
"""Resolution of the saved Videofile, not the camera itself."""
PROFILE = "high"
"""Profile used in h264 encoder."""
LEVEL = "4"
"""Level used in h264 encoder."""
BITRATE = 600000
"""Bitrate used in h264 encoder."""
QUALITY = 30
"""Quality used in h264 encoder."""

# hardware settings
USE_LED = False
"""True if Status-LEDs are connected."""
USE_BUTTONS = False
"""True if hardware buttons are connected."""
WIFIDELAY = 900
"""Delay in seconds before wifi turns off."""


def read_user_config(path_to_config: Union[str, Path]) -> dict:
    validate_user_config()

    if not Path(path_to_config).is_file():
        # TODO: read default config
        pass


def validate_user_config():
    pass
