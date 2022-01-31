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


from subprocess import call, run
from time import sleep

import config
import hardware.buttons as buttons
import hardware.camera as camera
import hardware.leds as leds
import status
import os

from helpers import log

log.write("rpi", level="debug")


def shutdown():
    """Shutdown the Raspberry Pi.

    Shuts down the Raspberry Pi if the power button is still pressed after blink ends
    (2 seconds).
    Tries to stop and close the camera object.
    Writes messages to the logfile.

    """
    log.write("Shutdown by button in 2s", False)
    status.noblink = True
    leds.power.blink(
        on_time=0.5,
        off_time=0.5,
        fade_in_time=0,
        fade_out_time=0,
        n=8,
        background=False,
    )
    leds.power.on()
    leds.wifi.off()
    if buttons.power.is_pressed:
        status.noblink = False
        log.write("Shutdown cancelled", False)
        return
    else:
        status.shutdownactive = True
        camera.stop_recording()
        log.breakline()
        log.write("Shutdown", False)
        log.breakline()
        log.closefile()
    call("sudo shutdown -h -t 0", shell=True)


def reboot():
    """Reboot the Raspberry Pi.

    Reboots the Raspberry Pi if any expection is raised.
    Tries to close the camera object and writes to logfile.

    """
    status.shutdownactive = True
    status.noblink = True
    leds.power.blink(
        on_time=0.1,
        off_time=0.1,
        fade_in_time=0,
        fade_out_time=0,
        n=None,
        background=True,
    )
    log.write("Reboot", False)
    log.breakline()
    log.closefile()
    camera.stop_recording()
    if not config.DEBUG:
        call("sudo reboot", shell=True)

def start_accesspoint():
    log.write("Wifiswitch")
    os.system("sudo systemctl start wpa_supplicant@ap0")
    time.sleep(10)



def wifi():
    """Switches the status of the Wifi-AP.

    If status.wifiapon is False, a script is started to turn the AP on.
    If status.wifiapon is True, it stops the AP after config.WIFIDELAY seconds.
    Uses a LED to signalize the status.

    """
    log.write("Wifiswitch")
    if buttons.wifi.is_pressed and not status.wifiapon:
        log.write("Turn WifiAP on")
        call("sudo /bin/bash /usr/local/bin/wifistart", shell=True)
        log.write("WifiAP on")
        leds.power.pulse(fade_in_time=0.25, fade_out_time=0.25, n=2, background=True)
        leds.wifi.blink(on_time=0.1, off_time=4.9, n=None, background=True)
        status.wifiapon = True
    elif not buttons.wifi.is_pressed and status.wifiapon:
        leds.power.pulse(fade_in_time=0.25, fade_out_time=0.25, n=2, background=True)
        if not config.DEBUG:
            sleep(config.WIFIDELAY)
        if not buttons.wifi.is_pressed and status.wifiapon:
            log.write("Turn WifiAP OFF")
            call("sudo systemctl stop hostapd.service", shell=True)
            call("sudo systemctl stop dnsmasq.service", shell=True)
            call("sudo ifconfig uap0 down", shell=True)
            log.write("WifiAP OFF")
            leds.wifi.off()
            status.wifiapon = False


def lowbattery():
    """Shutdown if battery is low.

    Shuts down the Raspberry Pi if called and writes a message to the logfile.

    """
    log.write("Low Battery", False)
    camera.stop_recording()
    status.shutdownactive = True
    log.breakline()
    log.write("Shutdown", False)
    log.breakline()
    log.closefile()
    call("sudo shutdown -h -t 0", shell=True)
