"""OTCamera main module.

Just calls the record function in record module.

Initializes the LEDs ans Wifi AP.

While it is recording time (see status.py), starts recording videos, splits them
every interval (see config.py), captures a new preview image and stops recording
after recording time ends.

Stops everthing by keyboard interrupt (Ctrl+C).

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


from record import record
#from hardware.camera import start_recording
from gui import gui

if __name__ == "__main__":
    record()
    #gui.main()
