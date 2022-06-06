"""OTCamera helpers to control the RPi interfaces.

Contains all functions to control the Raspberry Pi itself.

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


from subprocess import call

from OTCamera import config, status
from OTCamera.hardware import led
from OTCamera.hardware.camera import Camera
from OTCamera.helpers import log

log.write("imported rpi", level=log.LogLevel.DEBUG)
camera = Camera()


def shutdown():
    """Shutdown the Raspberry Pi.

    Shuts down the Raspberry Pi if the power button is still pressed after blink ends
    (2 seconds).
    Tries to stop and close the camera object.
    Writes messages to the logfile.

    """
    status.shutdownactive = True
    led.power_on()
    camera.stop_recording()
    log.breakline()
    log.write("Shutdown")
    log.breakline()
    log.closefile()
    call("sudo shutdown -h now", shell=True)


def reboot():
    """Reboot the Raspberry Pi.

    Reboots the Raspberry Pi if any exception is raised.
    Tries to close the camera object and writes to logfile.

    """
    status.shutdownactive = True
    status.noblink = True
    led.power.blink(
        on_time=0.1,
        off_time=0.1,
        fade_in_time=0,
        fade_out_time=0,
        n=None,
        background=True,
    )
    log.write("Reboot")
    log.breakline()
    log.closefile()
    camera.stop_recording()
    if not config.DEBUG_MODE_ON:
        call("sudo reboot", shell=True)


def wifi_switch_on():
    """Turn on Wi-Fi"""
    if not config.DEBUG_MODE_ON:
        call("rfkill unblock wlan", shell=True)
    led.wifi_on()
    status.wifi_on = True
    log.write("Wi-Fi on")


def wifi_switch_off():
    """Turn off Wi-Fi"""
    if not config.DEBUG_MODE_ON:
        call("rfkill block wlan", shell=True)
    led.wifi_off()
    status.wifi_on = False
    log.write("Wi-Fi off")
