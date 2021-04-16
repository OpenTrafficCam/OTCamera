"""OTCamera StromPi helper.

If StromPi is configured, lets you configure the StromPi, gets its status and shuts it
down.
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

# Based on the free software provided by [Joy-IT](https://github.com/joy-it/strompi3).
# Those parts are licensed under the MIT License.

import serial
from subprocess import call
from time import sleep


def print_current_config():
    """Get and print the currently active StromPi configuration."""
    current_config = _get_current_config()

    for conf in current_config:
        value = current_config[conf]
        if type(value) is bytes:
            value = value.decode(encoding="UTF-8", errors="strict")
        else:
            value = str(value)
        print(conf + ": " + value.rstrip("\n"))


def set_default_config():
    """Sets the default config for StromPi usage in OTC."""
    config = _default_config()
    configmap = _configmap()

    serial_port = _open_serial_port()
    breaks = 0.1
    breakl = 0.2

    for conf in config:
        conf_value = str(config[conf])
        msg = str.encode("set-config " + configmap[conf] + conf_value)
        serial_port.write(msg)
        sleep(breaks)
        serial_port.write(str.encode("\x0D"))
        sleep(breakl)

    serial_port.close()


def shutdown():
    breaks = 0.1
    breakl = 0.5

    serial_port = _open_serial_port()

    serial_port.write(str.encode("quit"))
    sleep(breaks)
    serial_port.write(str.encode("\x0D"))
    sleep(breakl)

    serial_port.write(str.encode("poweroff"))
    sleep(breaks)
    serial_port.write(str.encode("\x0D"))

    print("sudo shutdown -h now")
    print("Shutting down...")

    sleep(2)
    call("sudo shutdown -h -t 0", shell=True)


def _open_serial_port():
    """Open serial Port to StromPi

    Returns:
        serial_port: Serial Port, after use, close with serial_port.close()
    """
    serial_port = serial.Serial()

    serial_port.baudrate = 38400
    serial_port.port = "/dev/serial0"
    serial_port.timeout = 1
    serial_port.bytesize = 8
    serial_port.stopbits = 1
    serial_port.parity = serial.PARITY_NONE

    if serial_port.isOpen():
        serial_port.close()
    serial_port.open()

    return serial_port


def _get_current_config():
    """Open a serial port an retrive current StromPi config values.

    Returns:
        dict: {config name: value}
    """
    breaks = 0.1
    breakl = 0.5
    current_config = {}
    serial_port = _open_serial_port()
    serial_port.write(str.encode("quit"))
    sleep(breaks)
    serial_port.write(str.encode("\x0D"))
    sleep(breakl)

    serial_port.write(str.encode("status-rpi"))
    sleep(1)
    serial_port.write(str.encode("\x0D"))
    current_config["sp3_time"] = serial_port.readline(9999)
    current_config["sp3_date"] = serial_port.readline(9999)
    current_config["sp3_weekday"] = serial_port.readline(9999)
    current_config["sp3_modus"] = serial_port.readline(9999)
    current_config["sp3_alarm_enable"] = serial_port.readline(9999)
    current_config["sp3_alarm_mode"] = serial_port.readline(9999)
    current_config["sp3_alarm_hour"] = serial_port.readline(9999)
    current_config["sp3_alarm_min"] = serial_port.readline(9999)
    current_config["sp3_alarm_day"] = serial_port.readline(9999)
    current_config["sp3_alarm_month"] = serial_port.readline(9999)
    current_config["sp3_alarm_weekday"] = serial_port.readline(9999)
    current_config["sp3_alarmPoweroff"] = serial_port.readline(9999)
    current_config["sp3_alarm_hour_off"] = serial_port.readline(9999)
    current_config["sp3_alarm_min_off"] = serial_port.readline(9999)
    current_config["sp3_shutdown_enable"] = serial_port.readline(9999)
    current_config["sp3_shutdown_time"] = serial_port.readline(9999)
    current_config["sp3_warning_enable"] = serial_port.readline(9999)
    current_config["sp3_serialLessMode"] = serial_port.readline(9999)
    current_config["sp3_intervalAlarm"] = serial_port.readline(9999)
    current_config["sp3_intervalAlarmOnTime"] = serial_port.readline(9999)
    current_config["sp3_intervalAlarmOffTime"] = serial_port.readline(9999)
    current_config["sp3_batLevel_shutdown"] = serial_port.readline(9999)
    current_config["sp3_batLevel"] = serial_port.readline(9999)
    current_config["sp3_charging"] = serial_port.readline(9999)
    current_config["sp3_powerOnButton_enable"] = serial_port.readline(9999)
    current_config["sp3_powerOnButton_time"] = serial_port.readline(9999)
    current_config["sp3_powersave_enable"] = serial_port.readline(9999)
    current_config["sp3_poweroffMode"] = serial_port.readline(9999)
    current_config["sp3_poweroff_time_enable"] = serial_port.readline(9999)
    current_config["sp3_poweroff_time"] = serial_port.readline(9999)
    current_config["sp3_wakeupweekend_enable"] = serial_port.readline(9999)
    current_config["sp3_ADC_Wide"] = float(serial_port.readline(9999)) / 1000
    current_config["sp3_ADC_BAT"] = float(serial_port.readline(9999)) / 1000
    current_config["sp3_ADC_USB"] = float(serial_port.readline(9999)) / 1000
    current_config["sp3_ADC_OUTPUT"] = float(serial_port.readline(9999)) / 1000
    current_config["sp3_output_status"] = serial_port.readline(9999)
    current_config["sp3_powerfailure_counter"] = serial_port.readline(9999)
    current_config["sp3_firmwareVersion"] = serial_port.readline(9999)

    serial_port.close()

    return current_config


def _default_config():
    """Default config values for StromPi usage in OTC.

    Returns:
        dict: {config name: value}
    """
    config = {}
    config["sp3_modus"] = 3  # mUSB -> Battery
    config["sp3_shutdown_enable"] = 0
    config["sp3_shutdown_time"] = 30
    config["sp3_batLevel_shutdown"] = 1  # below 10 %
    config["sp3_serialLessMode"] = 0
    config["sp3_powersave_enable"] = 1
    config["sp3_warning_enable"] = 0
    config["sp3_powerOnButton_enable"] = 1
    config["sp3_poweroffMode"] = 1
    config["sp3_powerOnButton_time"] = 31
    config["sp3_alarmPoweroff"] = 0  # Power-Off Alarm
    config["sp3_alarm_enable"] = 0  # Wake-Up Alarm
    config["sp3_intervalAlarm"] = 0  # Interval-Alarm
    config["sp3_modusreset"] = 1  # eventually just 1 if modus really changed

    return config


def _configmap():
    """Maps a config name to the appropriate serial command.

    Returns:
        dict: {config name: serial command}
    """
    configmap = {}
    configmap["sp3_modusreset"] = "0 "
    configmap["sp3_modus"] = "1 "
    configmap["sp3_alarmPoweroff"] = "5 "
    configmap["sp3_alarm_enable"] = "13 "
    configmap["sp3_shutdown_enable"] = "14 "
    configmap["sp3_shutdown_time"] = "15 "
    configmap["sp3_warning_enable"] = "16 "
    configmap["sp3_serialLessMode"] = "17 "
    configmap["sp3_batLevel_shutdown"] = "18 "
    configmap["sp3_intervalAlarm"] = "19 "
    configmap["sp3_powerOnButton_enable"] = "22 "
    configmap["sp3_powerOnButton_time"] = "23 "
    configmap["sp3_powersave_enable"] = "24 "
    configmap["sp3_poweroffMode"] = "25 "
    configmap["sp3_poweroff_time"] = "27 "

    return configmap


if __name__ == "__main__":
    print_current_config()
    set_default_config()
    print_current_config()
