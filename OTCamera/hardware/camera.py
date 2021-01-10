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
from hardware import leds
from datetime import datetime as dt

from helpers import log, name
import config
import status
from helpers.filesystem import delete_old_files

log.write("Initializing Camera")

picam = picamera.PiCamera()
picam.framerate = config.FPS
picam.resolution = config.RESOLUTION
picam.annotate_background = picamera.Color("black")
picam.annotate_text = name.annotate()
picam.exposure_mode = config.EXPOSURE_MODE
picam.drc_strength = config.DRC_STRENGTH
picam.rotation = config.ROTATION

log.write("Camera initalized")


def start_recording():
    # TODO: exception handling
    delete_old_files()
    if not picam.recording:
        picam.annotate_text = name.annotate()
        picam.start_recording(
            output=name.video(),
            format=config.FORMAT,
            resize=config.RESIZE,
            profile=config.PROFILE,
            level=config.LEVEL,
            bitrate=config.BITRATE,
            quality=config.QUALITY,
        )
        log.write("started recording")
        wait_recording(2)
        capture()
        leds.rec_on()
    else:
        pass


def capture():
    picam.capture(
        name.preview,
        format=config.PREVIEWFORMAT,
        resize=config.RESIZE,
        use_video_port=True,
    )


def wait_recording(timeout=0):
    picam.wait_recording(timeout)


def __split():
    picam.split_recording(name.video())
    delete_old_files()
    log.write("splitted recording")


def intervalsplit():
    current_minute = dt.now().minute
    interval_minute = (current_minute % config.INTERVAL) == 0

    if interval_minute and status.new_interval:
        pass


def stop_recording():
    if picam.recording:
        picam.stop_recording()
        leds.rec_off()
        log.write("stopped recording")
