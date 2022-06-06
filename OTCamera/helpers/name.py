"""OTCamera helpers for (file)names.

Generates strings for use in different modules. For example the logfilename or
videofilename or the string to annotate the video.

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

import re
from datetime import datetime as dt
from pathlib import Path

from OTCamera import config


def video() -> str:
    """Filename of Video.

    Path incl. filename where videos are saved to, based on hostname and
    current date and time.

    Returns:
        str: filename for video
    """
    filename = Path(config.VIDEO_DIR) / f"{config.PREFIX}_{_current_dt()}.h264"
    return str(filename.expanduser().resolve())


def log() -> Path:
    """Filename of logfile.

    Path incl. filename where logfile is saved.

    Returns:
        Path: filename for log
    """
    filename = Path(config.VIDEO_DIR) / f"{config.PREFIX}_{_current_dt()}.log"
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


def get_date_from_log_file(log_filepath: Path) -> dt:
    regex = "[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}"
    timestamp = re.findall(pattern=regex, string=log_filepath.stem)[-1]
    date, time = timestamp.split("_")
    year, month, day = date.split("-")
    hour, minute, second = time.split("-")
    dt_object = dt(
        year=int(year),
        month=int(month),
        day=int(day),
        hour=int(hour),
        minute=int(minute),
        second=int(second),
    )
    return dt_object


if __name__ == "__main__":
    pass
