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


from time import sleep
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
    if not picam.recording:
        delete_old_files()
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
        __capture()
        leds.rec_on()
    else:
        pass


def __capture():
    picam.capture(
        name.preview(),
        format=config.PREVIEWFORMAT,
        resize=config.RESIZE,
        use_video_port=True,
    )
    log.write("preview captured", level="debug")


def wait_recording(timeout=0):
    if picam.recording:
        picam.wait_recording(timeout)
    else:
        sleep(timeout + 0.5)


def __split():
    picam.split_recording(name.video())
    delete_old_files()
    log.write("splitted recording")


def split_if_interval_ends():
    current_minute = dt.now().minute
    interval_minute = (current_minute % config.INTERVAL) == 0

    if interval_minute and status.new_interval:
        log.write("new interval", level="debug")
        __split()
        status.new_interval = False
        status.current_interval += 1
    elif not (interval_minute or status.new_interval):
        log.write("reset new interval", level="debug")
        status.new_interval = True


def preview():
    current_second = dt.now().second
    offset = 5
    preview_second = (current_second % config.PREVIEW_INTERVAL) == offset

    if preview_second and status.preview_on() and status.new_preview:
        log.write("new preview", level="debug")
        __capture()
        status.new_preview = False
    elif not (preview_second or status.new_preview):
        log.write("reset new preview", level="debug")
        status.new_preview = True


def stop_recording():
    if picam.recording:
        picam.stop_recording()
        leds.rec_off()
        log.write("stopped recording")
