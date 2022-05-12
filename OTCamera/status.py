"""OTCamera Status variables and functions.

Contains all status variables and functions to be used across multiple modules.

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


import re
import socket
import subprocess
from datetime import datetime as dt
from pathlib import Path
from typing import Union

from OTCamera import config
from OTCamera.helpers import log
from OTCamera.helpers.filesystem import calc_free_diskspace, resolve_path
from OTCamera.html_updater import ConfigData, ConfigHtmlId, StatusData, StatusHtmlId

log.write("status", level=log.LogLevel.DEBUG)

shutdownactive: bool = False
noblink: bool = False
wifiapon: bool = False
interval_finished: bool = False
more_intervals: bool = True
new_preview: bool = True
current_interval: int = 0
recording: bool = False

# Button statuses
power_button_pressed: bool = False
hour_button_pressed: bool = False
wifi_ap_button_pressed: bool = False
battery_is_low: bool = False


def record_time() -> bool:
    """Checks if the current hour is an hour to record.

    Returns True if the hour of the current time is either after configured start hour
    and before end hour or hardware button is switched to continuous record.

    Returns:
        bool: Time to record or not.
    """
    current_hour = dt.now().hour
    bytime = current_hour >= config.START_HOUR and current_hour < config.END_HOUR
    if config.USE_BUTTONS:
        record = hour_button_pressed or bytime
    else:
        record = bytime
    record = record and (not shutdownactive)
    return record


def preview_on() -> bool:
    """Checks if a preview image should be captured.

    Returns True if there are buttons configured and the WifiAP status is True.
    Returns always True if no buttons configured.

    Returns:
        bool: Capture new preview.
    """
    if config.USE_BUTTONS:
        return wifiapon
    else:
        return True


def get_status_data() -> StatusData:
    """Returns OTCamera's status information."""
    time = dt.now().strftime("%d.%m.%Y %H:%M:%S")
    hostname = socket.gethostname()
    free_diskspace = calc_free_diskspace(config.VIDEO_DIR)
    num_videos_recorded = _get_num_videos()
    currently_recording = recording
    wifi_active = _is_wifi_enabled()
    low_battery = battery_is_low
    power_button_active = power_button_pressed
    hour_button_active = hour_button_pressed
    wifi_ap_on = wifi_ap_button_pressed

    return StatusData(
        time=(StatusHtmlId.TIME, time),
        hostname=(StatusHtmlId.HOSTNAME, hostname),
        free_diskspace=(StatusHtmlId.FREE_DISKSPACE, free_diskspace),
        num_videos_recorded=(StatusHtmlId.NUM_VIDEOS_RECORDED, num_videos_recorded),
        currently_recording=(StatusHtmlId.CURRENTLY_RECORDING, currently_recording),
        wifi_active=(StatusHtmlId.WIFI_ACTIVE, wifi_active),
        low_battery=(StatusHtmlId.LOW_BATTERY, low_battery),
        power_button_active=(StatusHtmlId.POWER_BUTTON_ACTIVE, power_button_active),
        hour_button_active=(StatusHtmlId.HOUR_BUTTON_ACTIVE, hour_button_active),
        wifi_ap_on=(StatusHtmlId.WIFI_AP_ON, wifi_ap_on),
    )


def get_config_settings() -> ConfigData:
    """Returns OTCamera's configuration settings"""

    return ConfigData(
        debug_mode_on=(ConfigHtmlId.DEBUG_MODE_ON, config.DEBUG_MODE_ON),
        start_hour=(ConfigHtmlId.START_HOUR, config.START_HOUR),
        end_hour=(ConfigHtmlId.END_HOUR, config.END_HOUR),
        interval_video_split=(
            ConfigHtmlId.INTERVAL_VIDEO_SPLIT,
            config.INTERVAL_VIDEO_SPLIT,
        ),
        num_intervals=(ConfigHtmlId.NUM_INTERVALS, config.NUM_INTERVALS),
        preview_interval=(ConfigHtmlId.PREVIEW_INTERVAL, config.PREVIEW_INTERVAL),
        min_free_space=(ConfigHtmlId.MIN_FREE_SPACE, config.MIN_FREE_SPACE),
        prefix=(ConfigHtmlId.PREFIX, config.PREFIX),
        video_dir=(ConfigHtmlId.VIDEO_DIR, config.VIDEO_DIR),
        preview_path=(ConfigHtmlId.PREVIEW_PATH, config.PREVIEW_PATH),
        template_html_path=(ConfigHtmlId.TEMPLATE_HTML_PATH, config.TEMPLATE_HTML_PATH),
        index_html_path=(ConfigHtmlId.INDEX_HTML_PATH, config.INDEX_HTML_PATH),
        fps=(ConfigHtmlId.FPS, config.FPS),
        resolution=(ConfigHtmlId.RESOLUTION, config.RESOLUTION),
        exposure_mode=(ConfigHtmlId.EXPOSURE_MODE, config.EXPOSURE_MODE),
        drc_strength=(ConfigHtmlId.DRC_STRENGTH, config.DRC_STRENGTH),
        rotation=(ConfigHtmlId.ROTATION, config.ROTATION),
        awb_mode=(ConfigHtmlId.AWB_MODE, config.AWB_MODE),
        video_format=(ConfigHtmlId.VIDEO_FORMAT, config.VIDEO_FORMAT),
        preview_format=(ConfigHtmlId.PREVIEW_FORMAT, config.PREVIEW_PATH),
        res_of_saved_video_file=(
            ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE,
            config.RESOLUTION_SAVED_VIDEO_FILE,
        ),
        h264_profile=(ConfigHtmlId.H264_PROFILE, config.H264_PROFILE),
        h264_bitrate=(ConfigHtmlId.H264_BITRATE, config.H264_BITRATE),
        h264_quality=(ConfigHtmlId.H264_QUALITY, config.H264_QUALITY),
        use_led=(ConfigHtmlId.USE_LED, config.USE_LED),
        use_buttons=(ConfigHtmlId.USE_BUTTONS, config.USE_BUTTONS),
        wifi_delay=(ConfigHtmlId.WIFI_DELAY, config.WIFI_DELAY),
    )


def _is_wifi_enabled(network_device_name: str = "wlan0") -> bool:
    """
    Checks if WiFi is enabled.

    On Linux the WiFI network device is usually denoted by 'wlan0'.

    Args:
        network_device_name (str): The network device's name.

    Returns:
        True if WiFI enabled otherwise False.

    Raises:
        Exception: If unknown error occurs.
        NetworkDeviceDoesNotExistError: If network name doesn't exist.
    """
    cmd = f"ip link show {network_device_name}"
    p = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    out, error = p.communicate()
    if error:
        err_msg = f"Error: '{error} occured while checking WIFI status."
        log.write(err_msg, log.LogLevel.ERROR)
        raise Exception(err_msg)

    if re.search("state up", str(out), re.IGNORECASE):
        log.write("WiFi is up", log.LogLevel.DEBUG)
        return True
    elif re.search("state down", str(out), re.IGNORECASE):
        log.write("WiFi is down", log.LogLevel.DEBUG)
        return False
    elif re.search("(Device).*(does not exist)", str(out), re.IGNORECASE):
        log.write(
            f'Network device: "{network_device_name}" does not exist',
            log.LogLevel.WARNING,
        )
        return False


# TODO: ip address


def _get_num_videos(
    video_dir: Union[str, Path] = config.VIDEO_DIR, filetype: str = config.VIDEO_FORMAT
) -> int:
    """
    Returns the number of videos in a directory.

    Args:
        video_dir (Union[str, Path]): Path to directory containing the videos.
        filetype (str): The filetype of a video file.

    Returns:
        The number of videos in a directory.
    """
    video_dir = resolve_path(video_dir)
    if not Path(video_dir).is_dir():
        raise NotADirectoryError(f"'{video_dir}' is not a directory!")

    return len([f for f in video_dir.iterdir() if filetype in f.suffix])


if __name__ == "__main__":
    pass
