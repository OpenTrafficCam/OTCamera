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
from typing import Union

import picamerax as picamera

from OTCamera import config, status
from OTCamera.domain.camera import Camera
from OTCamera.hardware import led
from OTCamera.helpers import log, name
from OTCamera.helpers.filesystem import delete_old_files

log.write("imported camera", level=log.LogLevel.DEBUG)


class CameraController:
    """
    The camera controller class providing functionality such as starting or stopping
    a recording, capturing a preview image, or closing the camera

    Args:
        camera (Camera): The camera instance that the controller interacts with.
    """

    def __init__(self, camera: Camera) -> None:
        self._camera = camera

    def start_recording(self) -> None:
        """Start video recording.

        If picam isn't already recording:
        - Deletes old files until enough free space is available.
        - Starts a new recording on picam, using the config.py.
        - Waits 2 seconds and captures a preview image.
        - Turns on the record LED (if attached).

        """
        # TODO: exception handling
        # OSError Errno 28 No space left on device
        # PiCamera error
        # https://picamera.readthedocs.io/en/release-1.13/api_exc.html?highlight=exception

        if not self._camera.is_recording and not status.shutdownactive:
            delete_old_files()
            self.__set_annotation_text()
            self._camera.start_recording(
                save_file=name.video(),
                video_format=config.VIDEO_FORMAT,
                resolution=config.RESOLUTION_SAVED_VIDEO_FILE,
                bitrate=config.H264_BITRATE,
                h264_profile=config.H264_PROFILE,
                h264_level=config.H264_LEVEL,
                h264_quality=config.H264_QUALITY,
            )
            log.write(
                f"Picam recording: {self._camera.is_recording}",
                level=log.LogLevel.DEBUG,
            )
            log.write("started recording")
            led.rec_on()
            status.recording = True
            status.html_updated_after_recording = False
            self._wait_recording(2)
            self.capture()

    def capture(self) -> None:
        """Capture a preview image if the camera is recording."""
        if self._camera.is_recording:
            self.__set_annotation_text()
            self._camera.capture(
                save_file=name.preview(),
                image_format=config.PREVIEW_FORMAT,
                resolution=config.RESOLUTION_SAVED_VIDEO_FILE,
            )
            log.write("preview captured", level=log.LogLevel.DEBUG)
        else:
            log.write(
                "can not capture preview, camera not recording",
                level=log.LogLevel.WARNING,
            )

    def _wait_recording(self, timeout: Union[int, float] = 0) -> None:
        """Wait timeout seconds recording.

        Args:
            timeout (Union[int, float], optional): Timeout in seconds. Defaults to 0.
        """
        if self._camera.is_recording:
            self._camera.wait_recording(timeout)
        else:
            sleep(timeout)

    def _split(self) -> None:
        """Splits recording and deletes old video files if no disk space available."""
        self._camera.split_recording(name.video())
        delete_old_files()
        log.write("split recording")

    def split_if_interval_ends(self) -> None:
        """Splits the video file if the configured interval ends.

        An Interval is configured in config.py. If the current minute matches the
        interval length, the video file is split and a new file begins.
        Counts the full intervals already recorded. If the maximum number of intervals
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
        self.__set_annotation_text()

    def __set_annotation_text(self) -> None:
        self._camera.set_annotation_text(name.annotate())

    def _is_interval_minute(self) -> bool:
        """Checks if the current minute is the interval minute defined by
        `config.INTERVAL_LENGTH` and thus defines whether a video should be split
        or not.

        Returns:
            bool: `True` if the interval minute has been reached. Otherwise, `False`.
        """
        current_minute = dt.now().minute
        interval_minute = (current_minute % config.INTERVAL_LENGTH) == 0
        return interval_minute

    def _is_after_new_interval_minute(self) -> bool:
        """Checks if a minute has passed after an interval minute has been reached.

        Returns:
            bool: `True` if a minute has passed after the interval minute. Otherwise,
            `False`.
        """
        after_new_interval = not (
            self._is_interval_minute() or status.interval_finished
        )
        return after_new_interval

    def _is_new_interval(self) -> bool:
        """Checks if a new time interval started.

        Returns:
            bool: `True` if the new time interval started. Otherwise, `False`.
        """
        new_interval = (
            self._is_interval_minute()
            and status.interval_finished
            and status.more_intervals
        )
        return new_interval

    def stop_recording(self) -> None:
        """Stops the video recording.

        If the picamera is recording, the recording is stopped. Additionally, the record
        LED ist switched off (if configured).

        """
        if self._camera.is_recording:
            self._camera.stop_recording()
            led.rec_off()
            log.write("stopped recording")
            log.write("recorded {n} videos".format(n=status.current_interval))
            status.recording = False

    def close(self) -> None:
        """Closes `picamera.PiCamera` instance.

        Logs to the log file if OTCamera has been already closed. But won't do anything
        apart from that.
        """

        try:
            self._camera.close()
            log.write("PiCamera closed", log.LogLevel.DEBUG)
        except picamera.PiCameraClosed:
            log.write("Camera already closed.", level=log.LogLevel.DEBUG)
            pass

    def restart(self) -> None:
        """
        Restarts the internal camera instance by closing it and re-initializing it.

        The initialization is being done with the current set of parameters.
        """
        log.write("restarting camera")
        self._camera.reinitialize()
