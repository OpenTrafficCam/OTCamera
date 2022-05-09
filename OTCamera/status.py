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


from datetime import datetime as dt

from OTCamera import config
from OTCamera.helpers import log

log.write("status", level=log.LogLevel.DEBUG)

shutdownactive = False
noblink = False
wifiapon = False
interval_finished = False
more_intervals = True
new_preview = True
current_interval = 0
recording = False
button_hour_pressed = False


def record_time():
    """Checks if the current hour is an hour to record.

    Returns True if the hour of the current time is either after configured start hour
    and before end hour or hardware button is switched to continuous record.

    Returns:
        bool: Time to record or not.
    """
    current_hour = dt.now().hour
    bytime = current_hour >= config.STARTHOUR and current_hour < config.ENDHOUR
    if config.USE_BUTTONS:
        record = button_hour_pressed or bytime
    else:
        record = bytime
    record = record and (not shutdownactive)
    return record


def preview_on():
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
        return True
    elif re.search("state down", str(out), re.IGNORECASE):
        return False
    elif re.search("(Device).*(does not exist)", str(out), re.IGNORECASE):
        raise NetworkDeviceDoesNotExistError(f"Network device {network_device_name}")

if __name__ == "__main__":
    pass
