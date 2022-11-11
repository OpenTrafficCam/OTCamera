"""OTCamera main module to record videos.

This module can be used to record either some intervals or continuously.
It is configured by config.py.

"""
# Copyright (C) 2022 OpenTrafficCam Contributors
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


import errno
import signal
import sys
from datetime import datetime as dt
from pathlib import Path
from time import sleep
from typing import Union

from OTCamera import config, status
from OTCamera.hardware import button, led
from OTCamera.hardware.camera import Camera
from OTCamera.helpers import log, name
from OTCamera.helpers.filesystem import delete_old_files
from OTCamera.html_updater import (
    ConfigDataObject,
    ConfigHtmlId,
    LogDataObject,
    LogHtmlId,
    StatusWebsiteUpdater,
)

log.write("imported record", level=log.LogLevel.DEBUG)


class OTCamera:
    """The OTCamera class provides functionality to record videos using Raspberry Pi's
    camera module.
    """

    def __init__(
        self,
        camera: Camera,
        html_updater: StatusWebsiteUpdater,
        capture_preview_immediately: bool = False,
        video_dir: Union[str, Path] = config.VIDEO_DIR,
        log_dir: Union[str, Path] = config.VIDEO_DIR,
        num_log_files_html: int = config.NUM_LOG_FILES_HTML,
    ) -> None:
        """Constructor to initialise the OTCamera class.

        Args:
            camera (Camera): The Camera class to control the Raspberry Pi camera.
            html_updater (StatusWebsiteUpdater): The class providing functionality to
            update the status website.
            capture_preview_immediately (bool, optional): Whether to capture preview
            image immediately. Defaults to False.
            video_dir (Union[str, Path], optional): Path to the save directory of the
            videos recorded by OTCamera. Defaults to config.VIDEO_DIR.
            log_dir (Union[str, Path], optional): Path to the save directory of the log
            files. Defaults to config.VIDEO_DIR.
            num_log_files_html (int, optional): The number of logfiles to be displayed
            on the status website. Defaults to config.NUM_LOG_FILES_HTML.
        """
        self._camera = camera
        self._html_updater = html_updater
        self._capture_preview_immediately = capture_preview_immediately
        self._video_dir = Path(video_dir)
        self._log_dir = Path(log_dir)
        self._num_log_files_html = num_log_files_html
        self._shutdown = False

        self._register_shutdown_action()

        Path(self._video_dir).mkdir(exist_ok=True)

        # Initializes the LEDs and Wifi AP
        if config.OTCAMERA_VERSION is not None:
            log.write(f"OTCamera Version: {config.OTCAMERA_VERSION}")
        log.breakline()
        log.write("starting periodic record")
        led.power_blink()
        if config.USE_BUTTONS:
            button.init_wifi_button()

    def loop(self) -> None:
        """Record and split videos.

        While it is recording time (see status.py), starts recording videos, splits them
        every interval (see config.py), captures a new preview image and stops recording
        after recording time ends.

        """
        if (
            not status.power_button_pressed
            and status.power_button_pressed_time is not None
        ):
            button.handle_power_button_off_state()

        if (
            not status.wifi_button_pressed
            and status.wifi_on
            and status.wifi_button_pressed_time is not None
        ):
            button.handle_wifi_button_off_state()

        self._send_alive_signal()
        if status.record_time():
            self._camera.start_recording()
            self._camera.split_if_interval_ends()
            self._try_capture_preview()
        else:
            self._camera.stop_recording()
            self._html_updater.update_info(
                status.get_status_data(),
                self._get_config_settings(),
                status.recording,
                status.hour_button_pressed,
                status.external_power_connected,
            )
            sleep(0.5)

    def _send_alive_signal(self) -> None:
        """Sends alive signal every 5 seconds using the power LED."""
        current_second = dt.now().second
        alive_signal_interval = 5  # in seconds
        is_send_time = (current_second % alive_signal_interval) == 3

        if is_send_time and not status.power_led_blinked:
            log.write("blink power led", level=log.LogLevel.DEBUG)
            led.power_blink()
            status.power_led_blinked = True
        elif (not is_send_time) and status.power_led_blinked:
            log.write("reset power_led_blinked", level=log.LogLevel.DEBUG)
            status.power_led_blinked = False

    def _try_capture_preview(
        self,
    ) -> None:
        """Tries capturing a preview image.

        Captures a new preview image, if the current second matches the preview interval
        configured in config.py and the Wifi AP is turned on (otherwise, a preview would
        be useless).

        Args:
            now (bool, optional): Generate preview immediately. Defaults to False.
        """
        current_second = dt.now().second
        # To make sure that preview and split are not called in the same second
        # we use offset -1 second. Otherwise picamerax could crash.
        offset = config.PREVIEW_INTERVAL - 1
        is_preview_time = (current_second % config.PREVIEW_INTERVAL) == offset
        time_preview = is_preview_time and status.wifi_on and not status.preview_taken

        if (
            self._capture_preview_immediately or time_preview
        ) and not status.shutdownactive:
            log.write("new preview", level=log.LogLevel.DEBUG)
            self._camera.capture()
            self._html_updater.update_info(
                status.get_status_data(),
                self._get_config_settings(),
                status.recording,
                status.hour_button_pressed,
                status.external_power_connected,
            )
            status.preview_taken = True
        elif not (is_preview_time or not status.preview_taken):
            log.write("reset preview_taken", level=log.LogLevel.DEBUG)
            status.preview_taken = False

    def record(
        self,
    ) -> None:
        """Run init and record loop.

        Initializes the LEDs and Wifi AP.

        While it is recording time (see status.py), starts recording videos, splits them
        every interval (see config.py), captures a new preview image and stops recording
        after recording time ends.

        Stops everything by keyboard interrupt (Ctrl+C).

        """
        try:
            while status.more_intervals:
                try:
                    self.loop()
                except OSError as oe:
                    if oe.errno == errno.ENOSPC:  # errno: no space left on device
                        log.write(str(oe), level=log.LogLevel.EXCEPTION)
                        delete_old_files(video_dir=self._video_dir)
                    else:
                        log.write("OSError occured", level=log.LogLevel.ERROR)
                        raise

            log.write("Captured all intervals, stopping", level=log.LogLevel.INFO)
        except KeyboardInterrupt:
            log.write("Keyboard Interrupt, stopping", level=log.LogLevel.INFO)
        except Exception as e:
            log.write(f"{e}", level=log.LogLevel.EXCEPTION)
            raise
        finally:
            self._execute_shutdown()

    def _register_shutdown_action(
        self,
    ) -> None:
        """Register call backs to be executed on a signal interrupt or terminate."""
        # Code to execute once terminate or interrupt signal occurs
        log.write("Register callbacks on SIGINT and SIGTERM", log.LogLevel.DEBUG)
        signal.signal(signal.SIGTERM, self._execute_shutdown)

    def _get_config_settings(self) -> ConfigDataObject:
        """Get OTCamera's configuration settings.

        Returns:
            ConfigDataObject: OTCamera's configuration settings
        """

        return ConfigDataObject(
            debug_mode_on=(ConfigHtmlId.DEBUG_MODE_ON, config.DEBUG_MODE_ON),
            start_hour=(ConfigHtmlId.START_HOUR, config.START_HOUR),
            end_hour=(ConfigHtmlId.END_HOUR, config.END_HOUR),
            interval_video_split=(
                ConfigHtmlId.INTERVAL_VIDEO_SPLIT,
                config.INTERVAL_LENGTH,
            ),
            num_intervals=(ConfigHtmlId.NUM_INTERVALS, config.NUM_INTERVALS),
            preview_interval=(ConfigHtmlId.PREVIEW_INTERVAL, config.PREVIEW_INTERVAL),
            min_free_space=(ConfigHtmlId.MIN_FREE_SPACE, config.MIN_FREE_SPACE),
            prefix=(ConfigHtmlId.PREFIX, config.PREFIX),
            video_dir=(ConfigHtmlId.VIDEO_DIR, config.VIDEO_DIR),
            preview_path=(ConfigHtmlId.PREVIEW_PATH, config.PREVIEW_PATH),
            template_html_path=(
                ConfigHtmlId.TEMPLATE_HTML_PATH,
                config.TEMPLATE_HTML_PATH,
            ),
            index_html_path=(ConfigHtmlId.INDEX_HTML_PATH, config.INDEX_HTML_PATH),
            fps=(ConfigHtmlId.FPS, config.FPS),
            resolution=(ConfigHtmlId.RESOLUTION, config.RESOLUTION),
            exposure_mode=(ConfigHtmlId.EXPOSURE_MODE, config.EXPOSURE_MODE),
            drc_strength=(ConfigHtmlId.DRC_STRENGTH, config.DRC_STRENGTH),
            rotation=(ConfigHtmlId.ROTATION, config.ROTATION),
            awb_mode=(ConfigHtmlId.AWB_MODE, config.AWB_MODE),
            video_format=(ConfigHtmlId.VIDEO_FORMAT, config.VIDEO_FORMAT),
            preview_format=(ConfigHtmlId.PREVIEW_FORMAT, config.PREVIEW_FORMAT),
            res_of_saved_video_file=(
                ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE,
                config.RESOLUTION_SAVED_VIDEO_FILE,
            ),
            h264_profile=(ConfigHtmlId.H264_PROFILE, config.H264_PROFILE),
            h264_level=(ConfigHtmlId.H264_LEVEL, config.H264_LEVEL),
            h264_bitrate=(ConfigHtmlId.H264_BITRATE, config.H264_BITRATE),
            h264_quality=(ConfigHtmlId.H264_QUALITY, config.H264_QUALITY),
            use_led=(ConfigHtmlId.USE_LED, config.USE_LED),
            use_buttons=(ConfigHtmlId.USE_BUTTONS, config.USE_BUTTONS),
            wifi_delay=(ConfigHtmlId.WIFI_DELAY, config.WIFI_DELAY),
        )

    def _get_log_info(self, start_idx: int, num: int) -> LogDataObject:
        """Get OTCamera's log information.
        Args:
            start_idx (int): The start index specifies the log files to be considered.
            The log files are sorted after their time of creation in descending order.
            Meaning a start_idx of 1 ignores the newest log file.
            num (int): The num recent log files stasrting from `start_idx` to get their
            data from.
        Returns:
            LogDataObject: The log data stored as a `LogDataObject`.
        """
        recent_log_files = self._get_num_recent_log_files(start_idx, num)
        log_data = ""
        for log_file_path in recent_log_files:
            log_data += f"File: {log_file_path}\n"
            with open(log_file_path, "r") as log_file:
                log_data += log_file.read()
                log_data += "\n"

        return LogDataObject(log_data=(LogHtmlId.LOG_DATA, log_data))

    def _get_num_recent_log_files(self, start_idx: int, num: int) -> list[Path]:
        """Get  `num` first log files starting from `start_idx`.

        Args:
            start_idx (int): The start index specifies the log files to be considered.
            The log files are sorted after their time of creation in descending order.
            Meaning a start_idx of 1 ignores the newest log file.
            num (int): The num recent log files stasrting from `start_idx` to get their
            data from.

        Returns:
            list[Path]: The log `num` log file paths starting from index `start_idx`.
        """
        # Gather all log files paths in an ordered list
        log_filepaths = [f for f in self._log_dir.iterdir() if f.suffix == ".log"]
        # Log filepaths sorted in descending order with newest one at index 0
        sorted_log_filepaths = sorted(
            log_filepaths, key=name.get_datetime_from_filename, reverse=True
        )
        # Get num recent log files
        recent_log_files = sorted_log_filepaths[start_idx:num]
        recent_log_files.reverse()
        return recent_log_files

    def _execute_shutdown(self, *args):
        """Code to execute when stopping OTCamera.

        ### Following tasks are executed

        - Recording is being stopped
        - Camera is being closed
        - Offline information is being displayed on the status website
        - Log file is being closed
        """
        if self._shutdown:
            return

        log.write("Stopping OTCamera", level=log.LogLevel.INFO)
        status.shutdownactive = True
        # OTCamera teardown
        self._camera.stop_recording()
        self._camera.close()
        log.write("OTCamera stopped", level=log.LogLevel.INFO)
        self._shutdown = True
        log.closefile()
        self._html_updater.display_offline_info(
            self._get_log_info(0, self._num_log_files_html),
        )
        sys.exit(0)


def main() -> None:
    """Start running OTCamera."""
    camera = Camera()
    html_updater = StatusWebsiteUpdater(
        html_path=config.TEMPLATE_HTML_PATH,
        offline_html_path=config.OFFLINE_HTML_PATH,
        html_save_path=config.INDEX_HTML_PATH,
        status_info_id="status-info",
        config_info_id="config-info",
        log_info_id="log-info",
        debug_mode_on=config.DEBUG_MODE_ON,
    )
    otcamera = OTCamera(camera=camera, html_updater=html_updater)
    otcamera.record()


if __name__ == "__main__":
    main()
