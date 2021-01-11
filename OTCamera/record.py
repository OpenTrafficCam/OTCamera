# OTVision: record a video for specific time period
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


from time import sleep

import status
from hardware import camera, leds
from helpers import log


def init():
    log.breakline()
    log.write("starting periodic record")
    leds.power_on()
    # TODO: turn wifi AP on


def loop():
    if status.record_time():
        camera.start_recording()
        camera.split_if_interval_ends()
        camera.preview()
        camera.wait_recording(0.5)
    else:
        camera.stop_recording()
        sleep(0.5)


def record():
    try:
        init()

        while status.more_intervals:
            loop()

        log.write("Captured all intervals, stopping", level="warning")

    except (KeyboardInterrupt):
        log.write("Keyboard Interrupt, stopping", level="warning")

    camera.stop_recording()
    log.closefile()


if __name__ == "__main__":
    record()
