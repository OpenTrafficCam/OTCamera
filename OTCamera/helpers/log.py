"""OTCamera helper for logging.

Open a logfile, based on the name.log and write a message to it. Also prints all
messages.

Use log.write(msg) to write any message, log.breakline() to write a single line of #
or log.otc() to log and print a OpenTrafficCam logo.

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

import json
import traceback
from enum import Enum

import requests
from art import text2art

from OTCamera.config import (
    DEBUG_MODE_ON,
    MS_TEAMS_MAX_FAILED_SEND_ATTEMPTS,
    MS_TEAMS_WEBHOOK_URL,
    USE_MS_TEAMS_WEBHOOK,
)
from OTCamera.helpers import name


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    EXCEPTION = "EXCEPTION"

    def __str__(self) -> str:
        return str(self.value)


def write(msg: str, level: LogLevel = LogLevel.INFO, reboot: bool = True) -> None:
    """Write any message to logfile.

    Takes a message, adds date and time and writes it to a logfile (name.log).

    Args:
        msg (str): Message to be written.
        level (str): either "debug", "info", "warning", "error", "exception"
        reboot (bool, optional): Perform reboot if logging fails. Defaults to True.
    """
    global disable_ms_teams_on_failed_attempts

    if level == LogLevel.DEBUG:
        if not DEBUG_MODE_ON:
            return
    current_time = name._current_dt()
    msg = f"{current_time} {level}: {msg}"
    _write(msg, reboot)

    if failed_attempts >= MS_TEAMS_MAX_FAILED_SEND_ATTEMPTS:
        disable_ms_teams_on_failed_attempts = True

    if (
        USE_MS_TEAMS_WEBHOOK
        and level != LogLevel.DEBUG
        and MS_TEAMS_WEBHOOK_URL
        and not disable_ms_teams_on_failed_attempts
    ):
        _send_msg_to_ms_teams(msg, MS_TEAMS_WEBHOOK_URL, current_time)
    if level == LogLevel.EXCEPTION:
        _write(_get_stack_trace(), reboot)


def _send_msg_to_ms_teams(msg: str, teams_url: str, time: str) -> None:
    headers = {"Content-Type": "application/json"}
    payload = {"text": msg}
    err_prefix = f"{time} {LogLevel.ERROR}: "

    global failed_attempts

    try:
        response = requests.post(
            teams_url, headers=headers, data=json.dumps(payload), timeout=10
        )
        status_code = response.status_code
        if status_code in range(400, 600):
            err_msg = (
                f"{err_prefix}"
                f"Unable to send MS Teams message [Status Code {status_code}]"
            )
            _write(err_msg)
            failed_attempts += 1
        else:
            failed_attempts = 0

    except requests.exceptions.RequestException as e:
        _write_exception_msg(err_prefix, e)
        failed_attempts += 1


def _write_exception_msg(
    err_prefix: str,
    exception: Exception,
) -> None:
    _write(f"{err_prefix} {exception}")


def _get_stack_trace() -> str:
    return traceback.format_exc()


def breakline(reboot: bool = True) -> None:
    """Write a breakline.

    Write a breakline containing several # to the logfile.

    Args:
        reboot (bool, optional): Perform reboot if logging fails. Defaults to True.
    """
    msg = "\n############################\n"
    _write(msg)


def otc() -> None:
    """Generate a ASCII logo and write it to the logfile."""
    otclogo = text2art("OpenTrafficCam")
    _write(otclogo)


def _write(msg: str, reboot: bool = True) -> None:
    print(msg)
    logf.write(msg + "\n")
    logf.flush()


def closefile() -> None:
    """Flush and close the logfile."""
    logf.flush()
    logf.close()


def _check_log_path() -> None:
    logfile = name.log()
    logpath = logfile.parent
    if not logpath.exists():
        logpath.mkdir(parents=True)


_check_log_path()
logf = open(name.log(), "a")
otc()
breakline()
failed_attempts: int = 0
disable_ms_teams_on_failed_attempts: bool = False
