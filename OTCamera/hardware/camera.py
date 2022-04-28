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
from typing import Tuple, Union

import picamerax as picamera
from colorzero import Color

from OTCamera import config, status
from OTCamera.hardware import led
from OTCamera.helpers import log, name
from OTCamera.helpers.filesystem import delete_old_files


class Singleton(object):
    def __new__(cls, *args, **kwds):
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        it.init(*args, **kwds)
        return it

    def init(self, *args, **kwds):
        pass


class Camera(Singleton):
    def init(
        self,
        framerate: int = config.FPS,
        resolution: Tuple[int, int] = config.RESOLUTION,
        annotate_background: Color = Color("black"),
        exposure_mode: str = config.EXPOSURE_MODE,
        awb_mode: str = config.AWB_MODE,
        drc_strength: str = config.DRC_STRENGTH,
        rotation: int = config.ROTATION,
    ) -> None:
        log.write("Initializing Camera", level=log.LogLevel.DEBUG)

        self.framerate = framerate
        self.resolution = resolution
        self.annotate_background = annotate_background
        self.exposure_mode = exposure_mode
        self.awb_mode = awb_mode
        self.drc_strength = drc_strength
        self.rotation = rotation
        self._picam = self._create_picam()
        log.write("Camera initialized")

    # TODO: getter fuer recording

    def start_recording(self):
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

        if not self._picam.recording:
            delete_old_files()
            self._picam.annotate_text = name.annotate()
            self._picam.start_recording(
                output=name.video(),
                format=config.FORMAT,
                resize=config.RESIZE,
                profile=config.PROFILE,
                level=config.LEVEL,
                bitrate=config.BITRATE,
                quality=config.QUALITY,
            )
            log.write(f"Picam recording: {self._picam.recording}")
            log.write("started recording")
            self._wait_recording(2)
            self._capture()
            led.rec_on()
            status.recording = True
            # if fail
            # picam = init()

    def _capture(self):
        self._picam.annotate_text = name.annotate()
        self._picam.capture(
            name.preview(),
            format=config.PREVIEWFORMAT,
            resize=config.RESIZE,
            use_video_port=True,
        )
        log.write("preview captured", level=log.LogLevel.DEBUG)

    def _wait_recording(self, timeout: Union[int, float] = 0):
        if self._picam.recording:
            self._picam.wait_recording(timeout)
        else:
            sleep(timeout)

    def _split(self):
        self._picam.split_recording(name.video())
        delete_old_files()
        log.write("splitted recording")

    def split_if_interval_ends(self) -> None:
        """Splits the videofile if the configured intervals ends.

        An Interval is configured in config.py. If the current minute matches the
        interval length, the video file is split and a new file begins.
        Counts the full intervals already recorded. If the maximum number of intervals,
        configured in config.py is reached, recording stops by breaking the loop in
        record.py.

        """
        if self._new_interval():
            log.write("new interval", level=log.LogLevel.DEBUG)
            self._split()
            status.interval_finished = False
            status.current_interval += 1
            if config.N_INTERVALS > 0:
                status.more_intervals = status.current_interval < config.N_INTERVALS
            if not status.more_intervals:
                log.write("last interval", level=log.LogLevel.DEBUG)
        elif self._after_new_interval():
            status.interval_finished = True
            log.write("reset new interval", level=log.LogLevel.DEBUG)
        self._wait_recording(0.5)
        self._picam.annotate_text = name.annotate()

    def _interval_minute(self):
        current_minute = dt.now().minute
        interval_minute = (current_minute % config.INTERVAL) == 0
        return interval_minute

    def _after_new_interval(self):
        after_new_interval = not (self._interval_minute() or status.interval_finished)
        return after_new_interval

    def _new_interval(self):
        new_interval = (
            self._interval_minute()
            and status.interval_finished
            and status.more_intervals
        )
        return new_interval

    def preview(self, now: bool = False):
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
            log.write("new preview", level=log.LogLevel.DEBUG)
            self._capture()
            status.new_preview = False
        elif not (preview_second or status.new_preview):
            log.write("reset new preview", level=log.LogLevel.DEBUG)
            status.new_preview = True

    def stop_recording(self):
        """Stops the video recording.

        If the picamera is recording, the recording is stopped. Additionally, the record
        LED ist switched of (if configured).

        """
        if self._picam.recording:
            self._picam.stop_recording()
            led.rec_off()
            log.write("recorded {n} videos".format(n=status.current_interval))
            log.write("stopped recording")
            status.recording = False

    def close(self):
        self._picam.close()

    def restart(self):
        """
        Restarts the PiCamera instance by closing it and re-initialising it.

        The initialisation is being done with the current set of parameters.
        """
        log.write("Restart camera")
        try:
            self._picam.close()

        except picamera.PiCameraClosed:
            pass

        self._picam = self._create_picam()

    def _create_picam(self) -> picamera.PiCamera:
        picam = picamera.PiCamera()
        picam.framerate = self.framerate
        picam.resolution = self.resolution
        picam.annotate_background = self.annotate_background
        picam.exposure_mode = self.exposure_mode
        picam.awb_mode = self.awb_mode
        picam.drc_strength = self.drc_strength
        picam.rotation = self.rotation
        return picam
