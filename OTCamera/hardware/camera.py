"""OTCamera helper to handle picamera interaction.

Used to start, split and stop recording.

"""

# Copyright (C) 2023 OpenTrafficCam Contributors
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
from picamerax import Color

from OTCamera import config, status
from OTCamera.hardware import led
from OTCamera.helpers import log, name
from OTCamera.helpers.filesystem import delete_old_files

log.write("imported camera", level=log.LogLevel.DEBUG)


class Singleton(object):
    """Implements the Singleton design pattern.

    Classes inheriting from `Singleton` become a singleton class.
    Meaning only one instance is created.
    Constructing a another instance of the concrete class inheriting from `Singleton`
    will return the first instance.
    """

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
    """The camera class providing functionality such as starting or stopping a
    recording, capturing a preview image, or closing the camera

    Attributes:
        framerate (int, optional): The frame rate. Defaults to config.FPS.
        resolution (Tuple[int, int], optional): The resolution.
        Defaults to config.RESOLUTION.
        annotate_background (Color, optional): Color of text annotation background.
        Defaults to Color("black").
        exposure_mode (str, optional): The exposure mode. Defaults to
        config.EXPOSURE_MODE.
        awb_mode (str, optional): The awb mode. Defaults to config.AWB_MODE.
        drc_strength (str, optional): The DRC strength. Defaults to config.DRC_STRENGTH.
        rotation (int, optional): The image rotation. Defaults to config.ROTATION.
    """

    def init(
        self,
        framerate: int = config.FPS,
        resolution: Tuple[int, int] = config.RESOLUTION,
        annotate_background: Color = Color("black"),
        exposure_mode: str = config.EXPOSURE_MODE,
        awb_mode: str = config.AWB_MODE,
        drc_strength: str = config.DRC_STRENGTH,
        rotation: int = config.ROTATION,
        meter_mode: str = config.METER_MODE,
    ) -> None:
        log.write("Initializing Camera", level=log.LogLevel.DEBUG)

        self.framerate = framerate
        self.resolution = resolution
        self.annotate_background = annotate_background
        self.exposure_mode = exposure_mode
        self.awb_mode = awb_mode
        self.drc_strength = drc_strength
        self.rotation = rotation
        self.meter_mode = meter_mode
        self._picam = self._create_picam()
        log.write("Camera initialized", log.LogLevel.DEBUG)

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

        if not self._picam.recording and not status.shutdownactive:
            delete_old_files()
            self._picam.annotate_text = name.annotate()
            self._picam.start_recording(
                output=name.video(),
                format=config.VIDEO_FORMAT,
                resize=config.RESOLUTION_SAVED_VIDEO_FILE,
                profile=config.H264_PROFILE,
                level=config.H264_LEVEL,
                bitrate=config.H264_BITRATE,
                quality=config.H264_QUALITY,
            )
            log.write(
                f"Picam recording: {self._picam.recording}", level=log.LogLevel.DEBUG
            )
            log.write("started recording")
            led.rec_on()
            status.recording = True
            status.html_updated_after_recording = False
            self._wait_recording(2)
            self.capture()

    def capture(self):
        """Capture a preview image if camera is recording."""
        if self._picam.recording:
            self._picam.annotate_text = name.annotate()
            self._picam.capture(
                name.preview(),
                format=config.PREVIEW_FORMAT,
                resize=config.RESOLUTION_SAVED_VIDEO_FILE,
                use_video_port=True,
            )
            log.write("preview captured", level=log.LogLevel.DEBUG)
        else:
            log.write(
                "can not capture preview, camera not recording",
                level=log.LogLevel.WARNING,
            )

    def _wait_recording(self, timeout: Union[int, float] = 0):
        """Wait timeout seconds recording.

        Args:
            timeout (Union[int, float], optional): Timeout in seconds. Defaults to 0.
        """
        if self._picam.recording:
            self._picam.wait_recording(timeout)
        else:
            sleep(timeout)

    def _split(self):
        """Splits recording and deletes old video files if no disk space available."""
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
        if self._is_new_interval():
            log.write("new interval", level=log.LogLevel.DEBUG)
            self._split()
            status.interval_finished = False
            status.current_interval += 1
            if config.NUM_INTERVALS > 0:
                status.more_intervals = status.current_interval < config.NUM_INTERVALS
            if not status.more_intervals:
                log.write("last interval", level=log.LogLevel.DEBUG)
        elif self._is_after_new_interval_minute():
            status.interval_finished = True
            log.write("reset new interval", level=log.LogLevel.DEBUG)
        self._wait_recording(0.5)
        self._picam.annotate_text = name.annotate()

    def _is_interval_minute(self) -> bool:
        """Checks if the current minute is the interval minute defined by
        `config.INTERVAL_LENGTH` and thus defines whether a video should be splitted
        or not.

        Returns:
            bool: `True` if the interval minute has been reached. Otherwise `False`.
        """
        current_minute = dt.now().minute
        interval_minute = (current_minute % config.INTERVAL_LENGTH) == 0
        return interval_minute

    def _is_after_new_interval_minute(self) -> bool:
        """Checks if a minute has passed after an interval minute has been reached.

        Returns:
            bool: `True` if a minute has passed after the interval minute. Otherwise
            `False`.
        """
        after_new_interval = not (
            self._is_interval_minute() or status.interval_finished
        )
        return after_new_interval

    def _is_new_interval(self) -> bool:
        """Checks if a new time interval started.

        Returns:
            bool: `True` if new time interval started. Otherwise `False`.
        """
        new_interval = (
            self._is_interval_minute()
            and status.interval_finished
            and status.more_intervals
        )
        return new_interval

    def stop_recording(self):
        """Stops the video recording.

        If the picamera is recording, the recording is stopped. Additionally, the record
        LED ist switched of (if configured).

        """
        if self._picam.recording:
            self._picam.stop_recording()
            led.rec_off()
            log.write("stopped recording")
            log.write("recorded {n} videos".format(n=status.current_interval))
            status.recording = False

    def close(self):
        """Closes `picamera.PiCamera` instance.

        Logs to log file if OTCamera has been already closed. But won't do anything
        apart from that.
        """

        try:
            self._picam.close()
            log.write("PiCamera closed", log.LogLevel.DEBUG)
        except picamera.PiCameraClosed:
            log.write("Camera already closed.", level=log.LogLevel.DEBUG)
            pass

    def restart(self):
        """
        Restarts the PiCamera instance by closing it and re-initialising it.

        The initialisation is being done with the current set of parameters.
        """
        log.write("restarting camera")
        self.close()

        self._picam = self._create_picam()

    def _create_picam(self) -> picamera.PiCamera:
        """Creates PiCamera instance and initializes it with the camera settings passed
        to the OTCamera class.

        Returns:
            picamera.PiCamera: The PiCamera instance acting as the interface to control
            the physical picamera.
        """
        picam = picamera.PiCamera()
        picam.framerate = self.framerate
        picam.resolution = self.resolution
        picam.annotate_background = self.annotate_background
        picam.exposure_mode = self.exposure_mode
        picam.awb_mode = self.awb_mode
        picam.drc_strength = self.drc_strength
        picam.rotation = self.rotation
        picam.meter_mode = self.meter_mode
        return picam
