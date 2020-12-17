# OTCamera status variables
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

import datetime as dt
from OTCamera import config

shutdownactive = False
noblink = False
wifiapon = False


def record_time():
    current_hour = dt.datetime.now().hour
    record_time = (
        # TODO: #10 reference hardware config
        (hour_switch.is_pressed)
        or (current_hour >= config.STARTHOUR and current_hour < config.ENDHOUR)
    ) and (not shutdownactive)
    return record_time


def preview_on():
    return wifiapon


if __name__ == "__main__":
    pass
