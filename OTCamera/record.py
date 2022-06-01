"""OTCamera main module to record videos.

This module can be used to record either some intervals or continuously.
It is configured by config.py.

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
    OTCameraHTMLUpdater,
)

log.write("imported record", level=log.LogLevel.DEBUG)


class OTCamera:
    def __init__(
        self,
        camera: Camera,
        html_updater: OTCameraHTMLUpdater,
        capture_preview_immediately: bool = False,
        video_dir: Union[str, Path] = config.VIDEO_DIR,
        template_html_filepath: Union[str, Path] = config.TEMPLATE_HTML_PATH,
        index_html_filepath: Union[str, Path] = config.INDEX_HTML_PATH,
        offline_html_filepath: Union[str, Path] = config.OFFLINE_HTML_PATH,
        log_dir: Union[str, Path] = config.VIDEO_DIR,
        num_log_files_html: int = config.NUM_LOG_FILES_HTML,
    ) -> None:
        self._camera = camera
        self._html_updater = html_updater
        self._capture_preview_immediately = capture_preview_immediately
        self._video_dir = Path(video_dir)
        self._template_html_filepath = Path(template_html_filepath)
        self._index_html_filepath = Path(index_html_filepath)
        self._offline_html_filepath = Path(offline_html_filepath)
        self._log_dir = Path(log_dir)
        self._num_log_files_html = num_log_files_html
        self._shutdown = False

        self._register_shutdown_action()

        Path(self._video_dir).mkdir(exist_ok=True)

        # Initializes the LEDs and Wifi AP
        log.breakline()
        log.write("starting periodic record")
        led.power_on()
        button.init_wifi_button()

    def loop(self) -> None:
        """Record and split videos.

        While it is recording time (see status.py), starts recording videos, splits them
        every interval (see config.py), captures a new preview image and stops recording
        after recording time ends.

        """
        if status.record_time():
            self._camera.start_recording()
            self._camera.split_if_interval_ends()
            self._try_capture_preview()
        else:
            self._camera.stop_recording()
            sleep(0.5)

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
        offset = config.PREVIEW_INTERVAL - 1
        preview_second = (current_second % config.PREVIEW_INTERVAL) == offset
        time_preview = preview_second and status.wifi_on and status.new_preview

        if self._capture_preview_immediately or time_preview:
            log.write("new preview", level=log.LogLevel.DEBUG)
            self._camera.capture()
            self._html_updater.update_info(
                self._template_html_filepath,
                self._index_html_filepath,
                status.get_status_data(),
                self._get_config_settings(),
                self._get_log_info(start_idx=0, num=self._num_log_files_html),
            )
            status.new_preview = False
        elif not (preview_second or status.new_preview):
            log.write("reset new preview", level=log.LogLevel.DEBUG)
            status.new_preview = True

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
            log.write("Keyboard Interrupt, stopping", level=log.LogLevel.EXCEPTION)
        except Exception as e:
            log.write(f"{e}", level=log.LogLevel.EXCEPTION)
            raise
        finally:
            self._execute_shutdown()

    def _register_shutdown_action(
        self,
    ) -> None:
        # Code to execute once terminate or interrupt signal occurs
        log.write("Register callbacks on SIGINT and SIGTERM", log.LogLevel.DEBUG)
        signal.signal(signal.SIGINT, self._execute_shutdown)
        signal.signal(signal.SIGTERM, self._execute_shutdown)

    def _get_config_settings(self) -> ConfigDataObject:
        """Returns OTCamera's configuration settings"""

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
        # Gather all log files paths in an ordered list
        log_filepaths = [f for f in self._log_dir.iterdir() if f.suffix == ".log"]
        sorted_log_filepaths = sorted(
            log_filepaths, key=name.get_date_from_log_file, reverse=True
        )
        # Get num recent log files
        recent_log_files = sorted_log_filepaths[start_idx : num + 1]
        recent_log_files.reverse()
        log_data = ""
        for log_file_path in recent_log_files:
            log_data += f"File: {log_file_path}\n"
            with open(log_file_path, "r") as log_file:
                log_data += log_file.read()
                log_data += "\n"

        return LogDataObject(log_data=(LogHtmlId.LOG_DATA, log_data))

    def _execute_shutdown(self, *args):
        if self._shutdown:
            return

        log.write("Stopping OTCamera", level=log.LogLevel.INFO)
        # OTCamera teardown
        self._camera.stop_recording()
        self._camera.close()
        self._html_updater.display_offline_info(
            self._offline_html_filepath,
            self._index_html_filepath,
            self._get_log_info(0, self._num_log_files_html),
        )
        log.write("OTCamera stopped", level=log.LogLevel.INFO)
        self._shutdown = True
        log.closefile()
        sys.exit(0)


def main() -> None:
    camera = Camera()
    html_updater = OTCameraHTMLUpdater(
        status_info_id="status-info",
        config_info_id="config-info",
        log_info_id="log-info",
        debug_mode_on=config.DEBUG_MODE_ON,
    )
    otcamera = OTCamera(camera=camera, html_updater=html_updater)
    otcamera.record()


if __name__ == "__main__":
    main()
