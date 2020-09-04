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
from helpers import name

STARTHOUR = 6
ENDHOUR = 22

RESOLUTION = (1640, 1232)
RESIZE = (800, 600)
HOSTNAME = socket.gethostname()

MINFREESPACE = 1 #GB
VIDEOPATH = '/home/pi/videos/'
PREVIEWPATH = '/home/pi/webfiles/preview.jpg'

DEBUG = False

INTERVAL = 15
FPS = 20
PROFILE = 'high'
LEVEL = '4'
BITRATE = 600000
QUALITY = 30

WIFIDELAY = 900
