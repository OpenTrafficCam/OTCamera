"""OTCamera Status variables and functions.

Contains all status variables and functions to be used across multiple modules.

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


import re
import subprocess
from datetime import datetime as dt
from datetime import timedelta
from pathlib import Path
from typing import Union

from OTCamera import config
from OTCamera.helpers import log
from OTCamera.helpers.filesystem import calc_free_diskspace, resolve_path
from OTCamera.html_updater import StatusDataObject, StatusHtmlId

log.write("imported status", level=log.LogLevel.DEBUG)

shutdownactive: bool = False
noblink: bool = False
power_led_blinked: bool = False
wifi_on: bool = True
interval_finished: bool = False
more_intervals: bool = True
preview_taken: bool = False
current_interval: int = 0
recording: bool = False
power_button_pressed_time: Union[dt, None] = None
wifi_button_pressed_time: Union[dt, None] = None

# Button statuses
power_button_pressed: bool = False
hour_button_pressed: bool = False
wifi_button_pressed: bool = False
external_power_connected: bool = False
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


def get_status_data() -> StatusDataObject:
    """Returns OTCamera's status information."""
    free_diskspace = calc_free_diskspace(config.VIDEO_DIR) / (1024 * 1024 * 1024)
    num_videos_recorded = _get_num_videos()
    currently_recording = recording
    low_battery = battery_is_low
    hour_button_active = hour_button_pressed

    time_until_wifi_off = "--:--:--"
    if wifi_button_pressed_time is not None:
        wifi_delay = timedelta(seconds=config.WIFI_DELAY)
        time_until_wifi_off = str_format_timedelta(
            (wifi_button_pressed_time + wifi_delay) - dt.now()
        )

    return StatusDataObject(
        free_diskspace=(StatusHtmlId.FREE_DISKSPACE, f"{free_diskspace:.2f} GB"),
        num_videos_recorded=(StatusHtmlId.NUM_VIDEOS_RECORDED, num_videos_recorded),
        currently_recording=(StatusHtmlId.CURRENTLY_RECORDING, currently_recording),
        low_battery=(StatusHtmlId.LOW_BATTERY, low_battery),
        hour_button_active=(StatusHtmlId.HOUR_BUTTON_ACTIVE, hour_button_active),
        external_power_supply_connected=(
            StatusHtmlId.EXT_POWER_SUPPLY_CONNECTED,
            external_power_connected,
        ),
        ms_teams_webhook_enabled=(
            StatusHtmlId.MS_TEAMS_WEBHOOK_ENABLED,
            config.USE_MS_TEAMS_WEBHOOK,
        ),
        time_until_wifi_off=(
            StatusHtmlId.TIME_UNTIL_WIFI_OFF,
            time_until_wifi_off,
        ),
    )


def str_format_timedelta(time_delta: timedelta) -> str:
    """
    Converts a datetime.timedelta object as a string in the format of
    'HH:MM:SS'.

    Args:
        time_delta (timedelta): The time_delta object to be formatted.

    Returns:
        The timedelta in the format of 'HH:MM:SS' or '00:00:00' if negative.

    """
    total_seconds = time_delta.total_seconds()

    if time_delta is None or total_seconds <= 0:
        return "00:00:00"

    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):2}"


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
        err_msg = (
            f"Error: '{error} occured while checking {network_device_name} status."
        )
        log.write(err_msg, log.LogLevel.ERROR)
        return False
    if re.search("state up", str(out), re.IGNORECASE):
        log.write(f"{network_device_name} is up", log.LogLevel.DEBUG)
        return True
    elif re.search("state down", str(out), re.IGNORECASE):
        log.write(f"{network_device_name} is down", log.LogLevel.DEBUG)
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
