# OTCamera: LEDs and their functions.
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


from gpiozero import PWMLED
from config import USE_LED

from helpers import log


if USE_LED:

    POWERPIN = 13
    WIFIPIN = 12
    RECPIN = 5

    power = PWMLED(POWERPIN)
    wifi = PWMLED(WIFIPIN)
    rec = PWMLED(RECPIN)

    log.write("LEDs initalized")


def off():
    """[summary]"""
    power.on()
    wifi.on()
    rec.on()
