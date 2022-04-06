"""OTCamera helper fo filesystem stuff.

Check if enough filespace is available and delete old files until it's enough.

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


import os

import config
import psutil

from OTCamera.helpers import log

log.write("filesystem", level="debug")


def delete_old_files():
    """Delete old files until enough space available.

    Checks if enough space (config.MINFREESPACE) is a availabe to save video files.
    If not, deletes the oldest files in config.VIDEOPATH one after another until enough
    space is available on disk.

    """
    log.write("delete old file", level="debug")
    minfreespace = config.MINFREESPACE * 1024 * 1024 * 1024
    free_space = psutil.disk_usage(config.VIDEOPATH).free
    enough_space = free_space > minfreespace
    log.write("free space: {fs}".format(fs=free_space), level="DEBUG")
    log.write("min space: {ms}".format(ms=minfreespace), level="DEBUG")
    while not enough_space:
        oldest_video = min(os.listdir(config.VIDEOPATH), key=os.path.getctime)
        os.remove(config.VIDEOPATH + oldest_video)
        log.breakline()
        log.write("Deleted " + oldest_video)
        free_space = psutil.disk_usage("/").free
        log.write("free space: {fs}".format(fs=free_space), level="debug")
        enough_space = free_space > minfreespace
