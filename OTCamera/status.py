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
from hardware import buttons

shutdownactive = False
noblink = False
wifiapon = False
new_interval = False
new_preview = True


def record_time():
    current_hour = dt.datetime.now().hour
    bytime = current_hour >= config.STARTHOUR and current_hour < config.ENDHOUR
    if config.USE_BUTTONS:
        bybutton = buttons.hour.is_pressed
        record = bybutton or bytime
    else:
        record = bytime
    record = record and (not shutdownactive)
    return record


def preview_on():
    return wifiapon


if __name__ == "__main__":
    pass
