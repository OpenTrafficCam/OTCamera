# OTCamera: buttons config file to be imported.
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


from gpiozero import Button

POWERPIN = 6
HOURPIN = 19
WIFIPIN = 16
LOWBATTERYPIN = 18

def init():
    lowbattery_switch = Button(LOWBATTERYPIN, pull_up=True, hold_time=2, hold_repeat=False)
    power_switch = Button(POWERPIN, pull_up=False, hold_time=2, hold_repeat=False)
    hour_switch = Button(HOURPIN, pull_up=True, hold_time=2, hold_repeat=False)
    wifi_switch = Button(WIFIPIN, pull_up=True, hold_time=2, hold_repeat=False)
    lowbattery_switch.when_held = lowbattery
    power_switch.when_released = shutdown_rpi
    wifi_switch.when_held = wifi
    wifi_switch.when_released = wifi
    hour_switch.when_pressed = hour_switched
    hour_switch.when_released = hour_switched
