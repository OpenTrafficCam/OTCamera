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

# TODO: #49 use docstrings to describe the variables
DEBUG = False
"""Turn debug mode on to get addition log entries."""

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
VIDEOPATH = "/home/pi/videos/"
"""path to safe videofiles."""
PREVIEWPATH = "/home/pi/preview.jpg"
"""path to save preview."""


# camera settings
FPS = 20
RESOLUTION = (1640, 1232)
EXPOSURE_MODE = "nightpreview"
DRC_STRENGTH = "high"
ROTATION = 180
AWB_MODE = "greyworld"

# video settings
FORMAT = "h264"
PREVIEWFORMAT = "jpeg"
RESIZE = (800, 600)
PROFILE = "high"
LEVEL = "4"
BITRATE = 600000
QUALITY = 30

# hardware settings
USE_LED = False
USE_BUTTONS = False
WIFIDELAY = 900
