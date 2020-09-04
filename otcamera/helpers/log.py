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
    logfile.close()


def traceback():
    traceback.print_exc(file=logfile)
    logfile.write("\n")
