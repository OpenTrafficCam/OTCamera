"""OTCamera helper to interact with hardware buttons.

Initializes hardware buttons using gpiozero if configured in config.py.
Button callbacks are calling functions in rpi helper

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


from datetime import datetime as dt

from gpiozero import Button

from OTCamera import config, status
from OTCamera.helpers import log, rpi

log.write("buttons", level=log.LogLevel.DEBUG)


def its_record_time() -> bool:
    """Is it time to record or not?

    Determines if the current hour is an hour after start hour and before end hour
    configured in config.py as long as the hour button is not pressed. If pressed it's
    always recording time.

    Returns:
        bool: True if it is recording time
    """
    current_hour = dt.now().hour
    record_time = (
        (hour_button.is_pressed)
        or (current_hour >= config.START_HOUR and current_hour < config.END_HOUR)
    ) and (not status.SHUTDOWNACTIVE)
    return record_time


def _on_hour_button_switched() -> None:
    if hour_button.is_pressed:
        status.hour_button_pressed = True
        log.write("Hour Switch pressed")
    elif not hour_button.is_pressed:
        status.hour_button_pressed = False
        log.write("Hour Switch released")


def _on_low_battery_button_held() -> None:
    status.battery_is_low = True
    log.write("Battery level is low! Initiate shutdown!", log.LogLevel.WARNING)
    rpi.lowbattery()


def _on_power_button_released() -> None:
    assert not power_button.is_pressed
    status.power_button_pressed = False
    log.write("Power button released")
    rpi.shutdown()


def _on_wifi_ap_button_held() -> None:
    assert wifi_ap_button.is_pressed
    status.wifi_ap_button_pressed = True
    log.write("WiFi AP button pressed")
    rpi.wifi()


def _on_wifi_ap_button_released() -> None:
    assert not wifi_ap_button.is_pressed
    status.wifi_ap_button_pressed = False
    log.write("WiFi AP button released")
    rpi.wifi()


if config.USE_BUTTONS:

    log.write("Initalizing LEDs", level=log.LogLevel.DEBUG)

    POWERPIN = 6
    HOURPIN = 19
    WIFIPIN = 16
    LOWBATTERYPIN = 18

    low_battery_button = Button(
        LOWBATTERYPIN, pull_up=True, hold_time=2, hold_repeat=False
    )
    # Initialise buttons
    power_button = Button(POWERPIN, pull_up=False, hold_time=2, hold_repeat=False)
    hour_button = Button(HOURPIN, pull_up=True, hold_time=2, hold_repeat=False)
    wifi_ap_button = Button(WIFIPIN, pull_up=True, hold_time=2, hold_repeat=False)

    # Register callbacks
    low_battery_button.when_held = _on_low_battery_button_held
    power_button.when_released = _on_power_button_released
    wifi_ap_button.when_held = _on_wifi_ap_button_held
    wifi_ap_button.when_released = _on_wifi_ap_button_released
    hour_button.when_pressed = _on_hour_button_switched
    hour_button.when_released = _on_hour_button_switched

    # Set button statuses in status module
    status.power_button_pressed = power_button.is_pressed
    status.hour_button_pressed = hour_button.is_pressed
    status.wifi_ap_button_pressed = wifi_ap_button.is_pressed
    status.hour_button_pressed = hour_button.is_pressed

    log.write("Buttons initialized")

else:
    log.write("No Buttons")
