# OTCamera helpers to log information
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

from helpers import name, rpi


logfile = open(name.log(), "a")


def write_msg(msg, reboot=True):
    """
    Takes a message, adds date and time and writes it to a logfile (name.log).
    If msg is "#" date and time is not added and a series of '###' is written in the
    log.

    Args:
        msg (str): Message to be written. Use "#" to add a break.
        reboot (bool, optional): Perform reboot if logging fails. Defaults to True.
    """
    try:
        if msg == "#":
            msg = "############################"
        else:
            msg = "{t}: {msg}".format(t=name.current_t(), msg=msg)
        print(msg)
        logfile.write(msg + "\n")
        logfile.flush()
    except:
        print("PRINT AND LOG NOT POSSIBLE")
        if reboot:
            rpi.reboot()


def closefile():
    """
    Flush and close the logfile.
    """
    logfile.flush()
    logfile.close()


def traceback():
    """
    Write the traceback message to the logfile.
    """
    # TODO: #11 Test traceback function.
    traceback.print_exc(file=logfile)
    logfile.write("\n")
