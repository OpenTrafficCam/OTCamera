"""OTCamera helper for logging.

Open a logfile, based on the name.log and write a message to it. Also prints all
messages.

Use log.write(msg) to write any message, log.breakline() to write a single line of #
or log.otc() to log and print a OpenTrafficCam logo.

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


from art import text2art

from OTCamera.config import DEBUG
from OTCamera.helpers import name


def write(msg, level="info", reboot=True):
    """Write any message to logfile.

    Takes a message, adds date and time and writes it to a logfile (name.log).

    Args:
        msg (str): Message to be written.
        level (str): either "debug", "info", "warning", "error", "exception"
        reboot (bool, optional): Perform reboot if logging fails. Defaults to True.
    """
    level = level.upper()
    if level == "DEBUG":
        if not DEBUG:
            return
    msg = "{t} {level}: {msg}".format(
        t=name._current_dt(), level=level.upper(), msg=msg
    )
    _write(msg, reboot)


def breakline(reboot=True):
    """Write a breakline.

    Write a breakline containing several # to the logfile.

    Args:
        reboot (bool, optional): Perform reboot if logging fails. Defaults to True.
    """
    msg = "\n############################\n"
    _write(msg)


def otc():
    """Generate a ASCII logo and write it to the logfile."""
    otclogo = text2art("OpenTrafficCam")
    _write(otclogo)
    otcamera = text2art("OTCamera")
    _write(otcamera)


def _write(msg, reboot=True):
    print(msg)
    logf.write(msg + "\n")
    logf.flush()


def closefile():
    """Flush and close the logfile."""
    logf.flush()
    logf.close()


def _check_log_path():
    logfile = name.log()
    logpath = logfile.parent
    if not logpath.exists():
        logpath.mkdir(parents=True)


# TODO: #48 implement traceback handling and logging.#
# def _traceback():
#     """
#     Write the traceback message to the logfile.
#     """
#     # TODO: #11 Test traceback function.
#     traceback.print_exc(file=logfile)
#     logfile.write("\n")


_check_log_path()
logf = open(name.log(), "a")
otc()
breakline()
