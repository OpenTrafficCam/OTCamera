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
from pathlib import Path

import psutil

from OTCamera import config
from OTCamera.helpers import log

log.write("filesystem", level=log.LogLevel.DEBUG)


def delete_old_files():
    """Delete old files until enough space available.

    Checks if enough space (config.MINFREESPACE) is a availabe to save video files.
    If not, deletes the oldest files in config.VIDEOPATH one after another until enough
    space is available on disk.

    """
    absolute_video_path = str(Path(config.VIDEOPATH).expanduser().resolve())
    log.write("delete old file", level=log.LogLevel.DEBUG)
    min_free_space = config.MINFREESPACE * 1024 * 1024 * 1024

    while not _enough_space(min_free_space, absolute_video_path):
        oldest_video = min(os.listdir(absolute_video_path), key=os.path.getctime)
        os.remove(Path(absolute_video_path, oldest_video))
        log.breakline()
        log.write("Deleted " + oldest_video)
        free_space = psutil.disk_usage("/").free
        log.write("free space: {fs}".format(fs=free_space), level=log.LogLevel.DEBUG)


def _enough_space(min_free_space: int, video_path: str) -> bool:
    free_space = psutil.disk_usage(video_path).free
    log.write(f"free space: {free_space}", level=log.LogLevel.DEBUG)
    log.write(f"min space: {min_free_space}", level=log.LogLevel.DEBUG)
    return free_space > min_free_space
