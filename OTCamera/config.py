# OTCamera: static config file to be imported.
# Copyright (C) 2020 OpenTrafficCam Contributors
# <https://github.com/OpenTrafficCam
# <team@opentrafficcam.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import socket

# Turn debug mode on to get addition log entries
DEBUG = False

# Hour of day when to start/end recording
STARTHOUR = 6
ENDHOUR = 22
# Interval length in minutes before video splits
INTERVAL = 15
# Number of intervals to record (0=infinit)
N_INTERVALS = 2
# Interval between two preview images in seconds
PREVIEW_INTERVAL = 5

# free space on sd card before old videos get deleted
MINFREESPACE = 1  # GB
# prefix for videoname and annotation
PREFIX = socket.gethostname()
# path to safe videofiles
VIDEOPATH = "/home/pi/videos/"
# path to save preview
PREVIEWPATH = "/home/pi/preview.jpg"


# camera settings
FPS = 20
RESOLUTION = (1640, 1232)
EXPOSURE_MODE = "nightpreview"
DRC_STRENGTH = "high"
ROTATION = 180

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
