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
import status
from helpers import log


def shutdown():
    # TODO: #10 reference hardware config
    try:
        log.write_msg("Shutdown by button in 2s", False)
        status.noblink = True
        powerled.blink(
            on_time=0.5,
            off_time=0.5,
            fade_in_time=0,
            fade_out_time=0,
            n=8,
            background=False,
        )
        powerled.on()
        wifiled.off()
        # sleep(2)
        if power_switch.is_pressed:
            status.noblink = False
            log.write_msg("Shutdown cancelled", False)
            return
        else:
            status.shutdownactive = True
            try:
                if camera.recording:
                    camera.stop_recording()
                    recled.off()
                    camera.close()
                    log.write_msg("Stop record", False)
            except:
                log.write_msg("No camera", False)
            log.write_msg("#", False)
            log.write_msg("Shutdown", False)
            log.write_msg("#", False)
            log.closefile()
    except:
        log.write_msg("ERROR: Shutdown error", False)
        status.shutdownactive = False
    call("sudo shutdown -h -t 0", shell=True)


def reboot():
    # TODO: #10 reference hardware config
    try:
        status.shutdownactive = True
        status.noblink = True
        powerled.blink(
            on_time=0.1,
            off_time=0.1,
            fade_in_time=0,
            fade_out_time=0,
            n=None,
            background=True,
        )
        log.traceback()
        log.write_msg("Reboot", False)
        log.write_msg("#", False)
        log.closefile()
        camera.close()
    except:
        log.write_msg("ERROR: Reboot error", False)
    finally:
        sleep(1)
        print("Finally reboot")
        if not config.DEBUG:
            call("sudo reboot", shell=True)


def wifi():
    # TODO: #10 reference hardware config
    try:
        log.write_msg('Wifiswitch')
        if wifi_switch.is_pressed and not status.wifiapon:
            log.write_msg('Turn WifiAP on')
            call('sudo /bin/bash /usr/local/bin/wifistart', shell=True)
            log.write_msg('WifiAP on')
            powerled.pulse(fade_in_time=0.25, fade_out_time=0.25, n=2, background=True)
            wifiled.blink(on_time=0.1, off_time=4.9, n=None, background=True)
            status.wifiapon = True
        elif not wifi_switch.is_pressed and status.wifiapon:
            powerled.pulse(fade_in_time=0.25, fade_out_time=0.25, n=2, background=True)
            if not config.DEBUG:
                sleep(config.WIFIDELAY)
            if not wifi_switch.is_pressed and status.wifiapon:
                log.write_msg('Turn WifiAP OFF')
                call('sudo systemctl stop hostapd.service', shell=True)
                call('sudo systemctl stop dnsmasq.service', shell=True)
                call('sudo ifconfig uap0 down', shell=True)
                log.write_msg('WifiAP OFF')
                wifiled.off()
                status.wifiapon = False
    except:
        log.write_msg('#')
        log.write_msg('ERROR: Wifi Switch not possible')
        reboot()


def lowbattery():
# TODO: #10 reference hardware config
    try:
        log.write_msg("Low Battery", False)
        if camera.recording:
            camera.stop_recording()
            log.write_msg("Stop record", False)
        status.shutdownactive = True
        log.write_msg("#", False)
        log.write_msg("Shutdown", False)
        log.write_msg("#", False)
        log.closefile(
    except:
        log.write_msg("ERROR: Low Battery shutdown error", False)
    finally:
        call("sudo shutdown -h -t 0", shell=True)