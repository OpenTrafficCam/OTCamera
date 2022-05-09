"""OTCamera main module to record videos.

This module can be used to record either some intervals or continuously.
It is configured by config.py.

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


import errno
from time import sleep

from OTCamera import config, status
from OTCamera.hardware import led
from OTCamera.hardware.camera import Camera
from OTCamera.helpers import log
from OTCamera.helpers.filesystem import delete_old_files
from OTCamera.html_updater import OTCameraHTMLUpdater


def init():
    """Initializes the LEDs and Wifi AP."""
    log.breakline()
    log.write("starting periodic record")
    led.power_on()
    # TODO: turn wifi AP on #41


def loop(camera: Camera):
    """Record and split videos.

    While it is recording time (see status.py), starts recording videos, splits them
    every interval (see config.py), captures a new preview image and stops recording
    after recording time ends.

    """
    if status.record_time():
        camera.start_recording()
        camera.split_if_interval_ends()
        camera.preview()
    else:
        camera.stop_recording()
        sleep(0.5)


def record(
    camera: Camera = Camera(),
    video_dir: str = config.VIDEO_DIR,
    html_updater: OTCameraHTMLUpdater = OTCameraHTMLUpdater(debug_mode_on=config.DEBUG),
) -> None:
    """Run init and record loop.

    Initializes the LEDs and Wifi AP.

    While it is recording time (see status.py), starts recording videos, splits them
    every interval (see config.py), captures a new preview image and stops recording
    after recording time ends.

    Stops everything by keyboard interrupt (Ctrl+C).

    """
    try:
        init()

        while status.more_intervals:
            try:
                loop(camera)
            except OSError as oe:
                if oe.errno == errno.ENOSPC:  # errno: no space left on device
                    log.write(str(oe), level=log.LogLevel.EXCEPTION)
                    delete_old_files(video_dir=video_dir)
                else:
                    log.write("OSError occured", level=log.LogLevel.ERROR)
                    raise

        log.write("Captured all intervals, stopping", level=log.LogLevel.WARNING)
    except KeyboardInterrupt:
        log.write("Keyboard Interrupt, stopping", level=log.LogLevel.EXCEPTION)
    except Exception as e:
        log.write(f"{e}", level=log.LogLevel.EXCEPTION)
        raise
    finally:
        log.write("Execute teardown!", level=log.LogLevel.INFO)
        camera.stop_recording()
        camera.close()
        log.closefile()


def main() -> None:
    camera = Camera()
    video_dir = config.VIDEO_DIR
    html_updater = OTCameraHTMLUpdater(
        status_info_id="status-info",
        config_info_id="config-info",
        debug_mode_on=config.DEBUG,
    )
    record(camera, video_dir, html_updater)


if __name__ == "__main__":
    main()
