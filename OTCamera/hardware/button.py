"""OTCamera helper to interact with hardware buttons.

Initializes hardware buttons using gpiozero if configured in config.py.
Button callbacks are calling functions in rpi helper

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

from gpiozero import Button

from OTCamera import config, status
from OTCamera.helpers import log, rpi

log.write("buttons", level=log.LogLevel.DEBUG)


def its_record_time():
    """Is it time to record or not?

    Determines if the current hour is an hour after start hour and before end hour
    configured in config.py as long as the hour button is not pressed. If pressed it's
    always recording time.

    Returns:
        bool: True if it is recording time
    """
    current_hour = dt.now().hour
    record_time = (
        (hour.is_pressed)
        or (current_hour >= config.STARTHOUR and current_hour < config.ENDHOUR)
    ) and (not status.SHUTDOWNACTIVE)
    return record_time


def _hour_switched():
    if hour.is_pressed:
        status.button_hour_pressed = True
        log.write("Hour Switch pressed")
    elif not hour.is_pressed:
        status.button_hour_pressed = False
        log.write("Hour Switch released")


if config.USE_BUTTONS:

    log.write("Initalizing LEDs", level=log.LogLevel.DEBUG)

    POWERPIN = 6
    HOURPIN = 19
    WIFIPIN = 16
    LOWBATTERYPIN = 18

    lowbattery = Button(LOWBATTERYPIN, pull_up=True, hold_time=2, hold_repeat=False)
    power = Button(POWERPIN, pull_up=False, hold_time=2, hold_repeat=False)
    hour = Button(HOURPIN, pull_up=True, hold_time=2, hold_repeat=False)
    wifi = Button(WIFIPIN, pull_up=True, hold_time=2, hold_repeat=False)
    lowbattery.when_held = rpi.lowbattery
    power.when_released = rpi.shutdown
    wifi.when_held = rpi.wifi
    wifi.when_released = rpi.wifi
    hour.when_pressed = _hour_switched
    hour.when_released = _hour_switched
    status.button_hour_pressed = hour.is_pressed

    log.write("Buttons initialized")

else:
    log.write("No Buttons")
