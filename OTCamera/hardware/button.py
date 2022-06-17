"""OTCamera helper to interact with hardware buttons.

Initializes hardware buttons using gpiozero if configured in config.py.
Defines all button related functionality.

"""
# Copyright (C) 2022 OpenTrafficCam Contributors
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
from time import sleep

from gpiozero import Button

from OTCamera import config, status
from OTCamera.hardware import led
from OTCamera.helpers import log, rpi

log.write("imported buttons", level=log.LogLevel.DEBUG)


def _on_hour_button_switched() -> None:
    """_summary_"""
    if hour_button.is_pressed:
        status.hour_button_pressed = True
        log.write("Hour Switch pressed")
    elif not hour_button.is_pressed:
        status.hour_button_pressed = False
        log.write("Hour Switch released")


def _on_low_battery_button_held() -> None:
    status.battery_is_low = True
    log.write("Battery level is low!", log.LogLevel.WARNING)
    rpi.shutdown()


def _on_power_button_released() -> None:
    status.power_button_pressed = False
    log.write("Power button released", level=log.LogLevel.DEBUG)
    log.write("Shutdown by button initialized")
    status.noblink = True
    led.power_pre_off()
    timer = 0
    shutdown_delay = 5
    while timer <= shutdown_delay:
        if power_button.is_pressed:
            break
        sleep(1)
        timer += 1
    if not power_button.is_pressed:
        led.power_on()
        if config.DEBUG_MODE_ON:
            log.write("Mock shutting down RPI in debug mode.", log.LogLevel.DEBUG)
        else:
            rpi.shutdown()
    else:
        status.noblink = False
        log.write("Shutdown cancelled. Button pressed again.", False)
        led.power_blink()


def _on_wifi_button_pressed() -> None:
    status.wifi_button_pressed = True
    log.write("Wi-Fi button pressed")


def _on_wifi_button_held() -> None:
    status.wifi_button_pressed = True
    log.write("Wi-Fi button held", level=log.LogLevel.DEBUG)
    if not status.wifi_on:
        rpi.wifi_switch_on()


def _on_wifi_button_released() -> None:
    status.wifi_button_pressed = False
    log.write("Wi-Fi button released", level=log.LogLevel.DEBUG)
    if status.wifi_on:
        led.wifi_pre_off()
        log.write(f"Turning off Wi-Fi AP in {config.WIFI_DELAY} s")
        timer = 0
        while timer <= config.WIFI_DELAY:
            if wifi_button.is_pressed:
                break
            sleep(1)
            timer += 1
        if not wifi_button.is_pressed:
            rpi.wifi_switch_off()
        else:
            log.write("Wi-Fi not turned off. Button pressed again.")
            led.wifi_on()


def init_wifi_button():
    log.write("Initializing Wi-Fi", level=log.LogLevel.DEBUG)
    if wifi_button.is_pressed:
        rpi.wifi_switch_on()
    else:
        rpi.wifi_switch_off()


if config.USE_BUTTONS:

    log.write("Initalizing Buttons", level=log.LogLevel.DEBUG)

    POWERPIN = 6
    HOURPIN = 19
    WIFIPIN = 16
    LOWBATTERYPIN = 18

    low_battery_button = Button(
        LOWBATTERYPIN, pull_up=True, hold_time=2, hold_repeat=False
    )
    # Initialise buttons
    power_button = Button(
        POWERPIN, pull_up=False, hold_time=2, hold_repeat=False, bounce_time=0.5
    )
    hour_button = Button(
        HOURPIN, pull_up=True, hold_time=2, hold_repeat=False, bounce_time=0.5
    )
    wifi_button = Button(
        WIFIPIN, pull_up=True, hold_time=2, hold_repeat=False, bounce_time=0.5
    )

    # Register callbacks
    low_battery_button.when_held = _on_low_battery_button_held
    power_button.when_released = _on_power_button_released
    wifi_button.when_pressed = _on_wifi_button_pressed
    wifi_button.when_held = _on_wifi_button_held
    wifi_button.when_released = _on_wifi_button_released
    hour_button.when_pressed = _on_hour_button_switched
    hour_button.when_released = _on_hour_button_switched

    # Set button statuses in status module
    status.power_button_pressed = power_button.is_pressed
    status.hour_button_pressed = hour_button.is_pressed
    status.wifi_button_pressed = wifi_button.is_pressed
    status.hour_button_pressed = hour_button.is_pressed

    log.write("Buttons initialized")

else:
    log.write("No Buttons")
