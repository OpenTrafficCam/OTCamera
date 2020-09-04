# OTCamera helper functions to handle filesystem
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

import os

import psutil

import config
from helpers import log, rpi


def delete_old_files():
    """
    Checks if enough space (config.MINFREESPACE) is a availabe to save video files.
    If not, deletes the oldest files in config.VIDEOPATH one after another until enough
    space is available on disk.
    """
    minfreespace = config.MINFREESPACE * 1024 * 1024 * 1024
    enough_space = psutil.disk_usage("/").free > minfreespace
    while not enough_space:
        try:
            oldest_video = min(os.listdir(config.VIDEOPATH), key=os.path.getctime)
            os.remove(config.VIDEOPATH + oldest_video)
            log.write_msg("#")
            log.write_msg("Deleted " + oldest_video)
        except:
            log.write_msg("#")
            log.write_msg("ERROR: Cannot delete file")
            rpi.reboot()
        enough_space = psutil.disk_usage("/").free > minfreespace
