# OTCamera helper to generate different strings.
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

from datetime import datetime as dt
import config


def video():
    """
    Path incl. filename where videos are saved to, based on hostname and
    current date and time.

    Returns:
        str: filename for video
    """

    filename = config.VIDEOPATH + config.HOSTNAME + "_" + current_dt() + ".h264"
    return filename


def log():
    """
    Path incl. filename where logfile is saved.

    Returns:
        str: filename for log
    """

    filename = config.VIDEOPATH + config.HOSTNAME + "_" + current_dt() + ".log"
    return filename


def annotate():
    """
    Text to be added as annotation to video footage.

    Returns:
        str: annotation text
    """

    time_str = dt.now().strftime(config.HOSTNAME + " %d.%m.%Y %H:%M:%S")
    return time_str


# TODO: refactor time stuff in separate helper
def current_dt():
    """
    Generates current date and time.

    Returns:
        str: YYYY-mm-dd_HH-MM-SS
    """

    curr_dt = dt.now().strftime("%Y-%m-%d_%H-%M-%S")
    return curr_dt


def current_t():
    """
    Generates current time.

    Returns:
        str: HH-MM-SS
    """

    curr_t = dt.now().strftime("%H-%M-%S")
    return curr_t


def preview():
    """
    Path incl. filename where preview file is saved.

    Returns:
        str: filename for preview
    """
    return config.PREVIEWPATH


if __name__ == "__main__":
    config.VIDEOPATH = "local test video"
    config.HOSTNAME = "local test host"

    print("video: {str}".format(str=video()))
    print("log: {str}".format(str=log()))
    print("annotate: {str}".format(str=annotate()))
    print("current_dt: {str}".format(str=current_dt()))
