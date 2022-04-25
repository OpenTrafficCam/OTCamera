"""OTCamera helper to handle picamera interaction.

Used to start, split and stop recording.

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


from datetime import datetime as dt
from time import sleep

import picamerax as picamera

from OTCamera import config, status
from OTCamera.hardware import led
from OTCamera.helpers import log, name
from OTCamera.helpers.filesystem import delete_old_files

log.write("Initializing Camera", level="debug")

picam = picamera.PiCamera()
picam.framerate = config.FPS
picam.resolution = config.RESOLUTION
picam.annotate_background = picamera.Color("black")
picam.annotate_text = name.annotate()
picam.exposure_mode = config.EXPOSURE_MODE
picam.awb_mode = config.AWB_MODE
picam.drc_strength = config.DRC_STRENGTH
picam.rotation = config.ROTATION

log.write("Camera initalized")


def start_recording():
    """Start a recording a video.

    If picam isn't already recording:
    - Deletes old files, until enough free space is available.
    - Starts a new recording on picam, using the config.py.
    - Waits 2 seconds and caputres a preview image.
    - Turns on the record LED (if attached).

    """
    # TODO: exception handling
    # OSError Errno 28 No space left on device
    # PiCamera error
    # https://picamera.readthedocs.io/en/release-1.13/api_exc.html?highlight=exception
    ERRNO_NO_SPACE_LEFT_ON_DEVICE = 28
    try:

        if not picam.recording:
            pass
        delete_old_files()
        picam.start_recording(
            output=name.video(),
            format=config.FORMAT,
            resize=config.RESIZE,
            profile=config.PROFILE,
            level=config.LEVEL,
            bitrate=config.BITRATE,
            quality=config.QUALITY,
        )
        log.write(f"Picam recording: {picam.recording}")
        log.write("started recording")
        _wait_recording(2)
        _capture()
        led.rec_on()
        status.recording = True
    except OSError as oe:
        if oe.errno == ERRNO_NO_SPACE_LEFT_ON_DEVICE:
            delete_old_files()
        else:
            raise
    except picamera.PiCameraAlreadyRecording:
        pass


def _capture():
    picam.annotate_text = name.annotate()
    picam.capture(
        name.preview(),
        format=config.PREVIEWFORMAT,
        resize=config.RESIZE,
        use_video_port=True,
    )
    log.write("preview captured", level="debug")


def _wait_recording(timeout=0):
    if picam.recording:
        picam.wait_recording(timeout)
    else:
        sleep(timeout)


def _split():
    picam.split_recording(name.video())
    delete_old_files()
    log.write("splitted recording")


def split_if_interval_ends():
    """Splits the videofile if the configured intervals ends.

    An Interval is configured in config.py. If the current minute matches the interval
    length, the video file is split and a new file begins.
    Counts the full intervals already recorded. If the maximum number of intervals,
    configured in config.py is reached, recording stops by breaking the loop in
    record.py.

    """
    if _new_interval():
        log.write("new interval", level="debug")
        _split()
        status.interval_finished = False
        status.current_interval += 1
        if config.N_INTERVALS > 0:
            status.more_intervals = status.current_interval < config.N_INTERVALS
        if not status.more_intervals:
            log.write("last interval", level="debug")
    elif _after_new_interval():
        status.interval_finished = True
        log.write("reset new interval", level="debug")
    _wait_recording(0.5)
    picam.annotate_text = name.annotate()


def _interval_minute():
    current_minute = dt.now().minute
    interval_minute = (current_minute % config.INTERVAL) == 0
    return interval_minute


def _after_new_interval():
    after_new_interval = not (_interval_minute() or status.interval_finished)
    return after_new_interval


def _new_interval():
    new_interval = (
        _interval_minute() and status.interval_finished and status.more_intervals
    )
    return new_interval


def preview(now: bool = False):
    """Capture a preview image.

    Captures a new preview image, if the current second matches the preview interval
    configured in config.py and the Wifi AP is turned on (otherwise, a preview would
    be useless).

    Args:
        now (bool, optional): Generate preview immediately. Defaults to False.
    """
    current_second = dt.now().second
    offset = config.PREVIEW_INTERVAL - 1
    preview_second = (current_second % config.PREVIEW_INTERVAL) == offset
    time_preview = preview_second and status.preview_on() and status.new_preview

    if now or time_preview:
        log.write("new preview", level="debug")
        _capture()
        status.new_preview = False
    elif not (preview_second or status.new_preview):
        log.write("reset new preview", level="debug")
        status.new_preview = True


def stop_recording():
    """Stops the video recording.

    If the picamera is recording, the recording is stopped. Additionally, the record
    LED ist switched of (if configured).

    """
    if picam.recording:
        picam.stop_recording()
        led.rec_off()
        log.write("recorded {n} videos".format(n=status.current_interval))
        log.write("stopped recording")
        status.recording = False
