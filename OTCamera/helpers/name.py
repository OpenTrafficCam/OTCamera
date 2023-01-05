"""OTCamera helpers for (file)names.

Generates strings for use in different modules. For example the logfilename or
videofilename or the string to annotate the video.

"""
# Copyright (C) 2023 OpenTrafficCam Contributors
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

import re
from datetime import datetime as dt
from pathlib import Path
from typing import Union

from OTCamera import config


def video() -> str:
    """Filename of Video.

    Path incl. filename where videos are saved to, based on hostname and
    current date and time.

    Returns:
        str: filename for video
    """
    filename = (
        Path(config.VIDEO_DIR) / f"{config.PREFIX}_FR{config.FPS}_{_current_dt()}.h264"
    )
    return str(filename.expanduser().resolve())


def log() -> Path:
    """Filename of logfile.

    Path incl. filename where logfile is saved.

    Returns:
        Path: filename for log
    """
    filename = (
        Path(config.VIDEO_DIR) / f"{config.PREFIX}_FR{config.FPS}_{_current_dt()}.log"
    )
    return Path(filename).expanduser().resolve()


def annotate() -> str:
    """String to annotate video.

    Text to be added as annotation to video footage.
    Contains a Prefix and current datetime.

    Returns:
        str: annotation text
    """
    time_str = dt.now().strftime(config.PREFIX + " %d.%m.%Y %H:%M:%S")
    return time_str


# TODO: refactor time stuff in separate helper
def _current_dt() -> str:
    """Generates current date and time.

    Returns:
        str: YYYY-mm-dd_HH-MM-SS
    """
    curr_dt = dt.now().strftime("%Y-%m-%d_%H-%M-%S")
    return curr_dt


def preview() -> str:
    """Filename for preview image.

    Path incl. filename where preview file is saved.

    Returns:
        str: filename for preview
    """
    filename = config.PREVIEW_PATH
    return str(Path(filename).expanduser().resolve())


def get_datetime_from_filename(filename: Union[str, Path]) -> dt:
    """Retrieves the date and time from a filename

    Searches for "_yyyy-mm-dd_hh-mm-ss".

    Args:
        filename (str): filename with expression

    Returns:
        dt: datetime object
    """
    if isinstance(filename, Path):
        filename = filename.stem

    regex = "_([0-9]{4,4}-[0-9]{2,2}-[0-9]{2,2}_[0-9]{2,2}-[0-9]{2,2}-[0-9]{2,2})"
    match = re.search(regex, filename)
    if not match:
        return None

    # Assume that there is only one timestamp in the file name
    datetime_str = match.group(1)  # take group withtout underscore

    try:
        date_time = dt.strptime(datetime_str, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return None

    return date_time


def get_fps_from_filename(filename: str) -> int:
    """Get frame rate from file name using regex.
    Returns None if frame rate is not found in file name.

    Args:
        input_filename (str): file name

    Returns:
        int or None: frame rate in frames per second or None
    """
    # Get input fps frome filename

    match = re.search(r"_FR([\d]+)_", filename)
    if not match:
        return None

    return int(match.group(1))
