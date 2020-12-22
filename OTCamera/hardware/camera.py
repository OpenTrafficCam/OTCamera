# OTCamera: camera and their functions.
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


import picamera

from helpers import log, name
import config


cam = picamera.PiCamera()
cam.framerate = config.FPS
cam.resolution = config.RESOLUTION
cam.annotate_background = picamera.Color("black")
cam.annotate_text = name.annotate()
cam.exposure_mode = config.EXPOSURE_MODE
cam.drc_strength = config.DRC_STRENGTH
cam.rotation = config.ROTATION

log.write_msg("Camera initalized")