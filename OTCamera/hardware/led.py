"""OTCamera LED interaction helper.

If LEDs are configured in config.py this modules handels all the interaction (on, off,
blinking) of the LEDs.

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


from gpiozero import PWMLED

from OTCamera import config
from OTCamera.helpers import log

log.write("imported led", level=log.LogLevel.DEBUG)


def off():
    """Turn all LEDs off."""
    if config.USE_LED:
        power.on()
        wifi.on()
        rec.on()
    else:
        pass


def rec_on():
    """Blink record LED infinite."""
    if config.USE_LED:
        rec.off()
        rec.blink(on_time=0.1, off_time=4.9, n=None, background=True)
    else:
        pass


def rec_off():
    """Pulse record LED 4 times and switch it off."""
    if config.USE_LED:
        rec.off()
        rec.pulse(fade_in_time=0.25, fade_out_time=0.25, n=4, background=True)
    else:
        pass


def power_on():
    """Blink power LED infinite."""
    if config.USE_LED:
        rec.off()
        power.blink(on_time=0.1, off_time=0, n=1, background=True)
    else:
        pass


def wifi_on():
    """Blink Wi-Fi LED infinite."""
    if config.USE_LED:
        wifi.off()
        wifi.blink(on_time=0.1, off_time=4.9, n=None, background=True)
    else:
        pass


def wifi_off():
    """Pulse Wi-Fi LED 4 times and switch it off."""
    if config.USE_LED:
        wifi.off()
        wifi.pulse(fade_in_time=0.25, fade_out_time=0.25, n=4, background=True)
    else:
        pass


def wifi_pre_off():
    """Pulse Wi-Fi LED 2 times and rapidly blink again."""
    if config.USE_LED:
        wifi.off()
        wifi.pulse(fade_in_time=0.25, fade_out_time=0.25, n=2, background=True)
        wifi.blink(on_time=0.1, off_time=0.9, n=None, background=True)
    else:
        pass


if config.USE_LED:

    log.write("Initializing LEDs", level=log.LogLevel.DEBUG)

    POWERPIN = 13
    WIFIPIN = 12
    RECPIN = 5

    power = PWMLED(POWERPIN)
    wifi = PWMLED(WIFIPIN)
    rec = PWMLED(RECPIN)

    off()

    log.write("LEDs initialized")

else:
    log.write("No LEDs")
