# OTCamera: Buttons and their functions.
# Copyright (C) 2020 OpenTrafficCam Contributors
# <https://github.com/OpenTrafficCam
# <team@opentrafficcam.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import datetime as dt

import config
import helpers.rpi as rpi
from gpiozero import Button
from helpers import log

import status

if config.USE_BUTTONS:

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
    hour.when_pressed = rpi.hour_switched
    hour.when_released = rpi.hour_switched

    log.write("Buttons initialized")


def its_record_time():
    current_hour = dt.datetime.now().hour
    record_time = (
        (hour.is_pressed)
        or (current_hour >= config.STARTHOUR and current_hour < config.ENDHOUR)
    ) and (not status.SHUTDOWNACTIVE)
    return record_time


def hour_switched():
    if hour.is_pressed:
        log.write("Hour Switch pressed")
    elif not hour.is_pressed:
        log.write("Hour Switch released")
