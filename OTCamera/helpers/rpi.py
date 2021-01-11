# OTCamera helper functions to control Raspberry Pi hardware features.
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

from subprocess import call
from time import sleep

import config
import hardware.buttons as buttons
import hardware.camera as cam
import hardware.leds as leds
import status

from helpers import log


log.write("rpi", level="debug")


def shutdown():
    """
    Shuts down the Raspberry Pi if the power button is still pressed after blink ends
    (2 seconds).
    Tries to stop and close the camera object.
    Writes messages to the logfile.
    """
    try:
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
        # sleep(2)
        if buttons.power.is_pressed:
            status.noblink = False
            log.write("Shutdown cancelled", False)
            return
        else:
            status.shutdownactive = True
            try:
                if cam.recording:
                    cam.stop_recording()
                    leds.rec.off()
                    cam.close()
                    log.write("Stop record", False)
            except:
                log.write("No camera", False)
            log.write("#", False)
            log.write("Shutdown", False)
            log.write("#", False)
            log.closefile()
    except:
        log.write("ERROR: Shutdown error", False)
        status.shutdownactive = False
    call("sudo shutdown -h -t 0", shell=True)


def reboot():
    """
    Reboots the Raspberry Pi if any expection is raised.
    Tries to close the camera object and writes to logfile.
    """
    try:
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
        log.traceback()
        log.write("Reboot", False)
        log.write("#", False)
        log.closefile()
        cam.close()
    except:
        log.write("ERROR: Reboot error", False)
    finally:
        sleep(1)
        print("Finally reboot")
        if not config.DEBUG:
            call("sudo reboot", shell=True)


def wifi():
    """
    Switches the status of the Wifi-AP.
    If status.wifiapon is False, a script is started to turn the AP on.
    If status.wifiapon is True, it stops the AP after config.WIFIDELAY seconds.
    Uses a LED to signalize the status.
    """
    try:
        log.write("Wifiswitch")
        if buttons.wifi.is_pressed and not status.wifiapon:
            log.write("Turn WifiAP on")
            call("sudo /bin/bash /usr/local/bin/wifistart", shell=True)
            log.write("WifiAP on")
            leds.power.pulse(
                fade_in_time=0.25, fade_out_time=0.25, n=2, background=True
            )
            leds.wifi.blink(on_time=0.1, off_time=4.9, n=None, background=True)
            status.wifiapon = True
        elif not buttons.wifi.is_pressed and status.wifiapon:
            leds.power.pulse(
                fade_in_time=0.25, fade_out_time=0.25, n=2, background=True
            )
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
    except:
        log.breakline()
        log.write("ERROR: Wifi Switch not possible")
        reboot()


def lowbattery():
    """
    Shuts down the Raspberry Pi if called and writes a message to the logfile.
    """
    try:
        log.write("Low Battery", False)
        if cam.recording:
            cam.stop_recording()
            log.write("Stop record", False)
        status.shutdownactive = True
        log.write("#", False)
        log.write("Shutdown", False)
        log.write("#", False)
        log.closefile()
    except:
        log.write("ERROR: Low Battery shutdown error", False)
    finally:
        call("sudo shutdown -h -t 0", shell=True)
