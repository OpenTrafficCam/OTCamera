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


from pathlib import Path
from typing import Union

import psutil

from OTCamera import config
from OTCamera.helpers import log
from OTCamera.helpers.errors import NoMoreFilesToDeleteError

log.write("filesystem", level=log.LogLevel.DEBUG)


def delete_old_files(
    video_dir: Union[str, Path] = config.VIDEO_DIR,
    min_free_space: int = config.MIN_FREE_SPACE,
) -> None:
    """Delete old files until enough space available.

    Checks if enough space (`config.MINFREESPACE`) is a availabe to save video files.
    If not, deletes the oldest files in `video_dir` one after another until enough
    space is available on disk.

    Args:
        video_dir (Union[str, Path], optional): Path to video directory.
        Defaults to `config.VIDEO_DIR`.
        min_free_space(int, optional): free space in GB on sd card before old videos
        get deleted.

    Raises:
        NoMoreFilesToDeleteError: If no more files in `video_dir` can be deleted to
        free up more space as the directory is empty.
        This implies that there is no space left

    """
    absolute_video_dirpath = Path(video_dir).expanduser().resolve()
    log.write("delete old file", level=log.LogLevel.DEBUG)
    min_free_space = min_free_space * 1024 * 1024 * 1024

    while not _enough_space(absolute_video_dirpath, min_free_space):
        video_paths = [
            f for f in absolute_video_dirpath.iterdir() if f.suffix != ".log"
        ]
        if len(video_paths) <= 1:
            log.write(
                (
                    "No more video files to be deleted "
                    f"in directory '{absolute_video_dirpath}'."
                )
            )
            raise NoMoreFilesToDeleteError(
                (
                    f"Folder: '{absolute_video_dirpath}' is empty. "
                    "No more files to be deleted.\n"
                    "Please make space to resume recording."
                )
            )
        oldest_video = min(video_paths, key=(lambda path: path.stat().st_ctime))
        oldest_video.unlink()
        log.breakline()
        log.write(f"Deleted {oldest_video}")
        free_space = psutil.disk_usage(absolute_video_dirpath).free
        log.write(f"free space: {free_space}", level=log.LogLevel.DEBUG)


def _enough_space(directory: Path, min_free_space: int) -> bool:
    free_space = psutil.disk_usage(directory).free
    log.write(f"free space: {free_space}", level=log.LogLevel.DEBUG)
    log.write(f"min space: {min_free_space}", level=log.LogLevel.DEBUG)
    return free_space > min_free_space
