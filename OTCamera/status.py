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
from OTCamera.hardware import button
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
        bybutton = button.hour.is_pressed
        record = bybutton or bytime
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


if __name__ == "__main__":
    pass
