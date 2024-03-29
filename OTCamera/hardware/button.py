"""OTCamera helper to interact with hardware buttons.

Initializes hardware buttons using gpiozero if configured in config.py.
Defines all button callback functions.
Also includes the basic logic behind button interactions.

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


from datetime import datetime as dt
from datetime import timedelta

from gpiozero import Button

from OTCamera import config, status
from OTCamera.hardware import led
from OTCamera.helpers import log, rpi

log.write("imported buttons", level=log.LogLevel.DEBUG)


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
    """Sets `status.hour_button_pressed` if `hour.button` is pressed or released.

    Used to determine if user want's to record 24/7 or time based.
    """
    if hour_button.is_pressed:
        status.hour_button_pressed = True
        log.write("Hour Switch pressed")
    elif not hour_button.is_pressed:
        status.hour_button_pressed = False
        log.write("Hour Switch released")


def _on_low_battery_button_held() -> None:
    """Shuts down Raspberry Pi if internal battery level is low.

    Adafruit's PowerBoost 1000C has two inputs: USB and LiPo-cell.
    If LiPo-cell voltage is below threshold, the 1000C Low Voltage PIN is pulled up.
    The 1000C PIN is connected to GPIO 18 through OTCamera pcb.
    Additionally sets `status.battery_is_low` to `True`.
    """
    status.battery_is_low = True
    log.write("Battery level is low!", log.LogLevel.WARNING)
    rpi.shutdown()


def _on_external_power_button_pressed() -> None:
    status.external_power_connected = True
    log.write("External power connected", log.LogLevel.INFO)


def _on_external_power_button_released() -> None:
    status.external_power_connected = False
    log.write("External power disconnected!", log.LogLevel.WARNING)


def _on_power_button_pressed() -> None:
    status.power_button_pressed = True
    status.power_button_pressed_time = None
    status.noblink = False
    log.write("Shutdown cancelled. Button pressed again.", log.LogLevel.INFO, False)
    led.power_blink()


def _on_power_button_released() -> None:
    """Shuts down Raspberry Pi after 5 seconds delay if main switch is switched off.

    If `power_button`is released the power led will blink for 5 seconds.
    If it's still released the Pi will shutdown.
    If `power_button` is pressed within the 5 seconds the shutdown will be canceled.
    """
    status.power_button_pressed = False
    status.power_button_pressed_time = dt.now()
    log.write("Power button released", level=log.LogLevel.DEBUG)
    log.write("Shutdown by button initialized")
    status.noblink = True
    led.power_pre_off()


def _on_wifi_button_pressed() -> None:
    """If `wifi_button` is pressed `status.wifi_button_pressed` will be set `True`.

    This callback function won't do anything else. See `_on_wifi_button_held`.
    """
    status.wifi_button_pressed = True
    log.write("Wi-Fi button pressed")


def _on_wifi_button_held() -> None:
    """If `wifi_button` is pressed for a certain time Wi-Fi will be turned on.

    The threshold to distinguish between "pressed" and "hold" is set during
    initialization (`hold_time=2`).
    """
    status.wifi_button_pressed = True
    status.wifi_button_pressed_time = None
    log.write("Wi-Fi button held", level=log.LogLevel.DEBUG)
    rpi.wifi_switch_on()


def _on_wifi_button_released() -> None:
    """If `wifi_button` is released Wi-Fi will be turned off after a delay.

    After releasing `wifi_button` the Wi-Fi LED will blink until a delay is over.
    The delay is configured in config.py (`config.WIFI_DELAY`).
    If `wifi_button` is pressed again within the delay Wi-Fi LED will blink slowly to
    indicate Wi-Fi is still on.
    If `wifi_button` is released for whole delay Wi-Fi will be turned off.
    """
    log.write("Wi-Fi button released", level=log.LogLevel.DEBUG)
    status.wifi_button_pressed = False
    status.wifi_button_pressed_time = dt.now()

    led.wifi_pre_off()
    log.write(f"Turning off Wi-Fi AP in {config.WIFI_DELAY} s")


def init_wifi_button():
    """Helper to initialize Wi-Fi status on boot according to `wifi_button`

    At boot time Wi-Fi will always be started by `rc.local`.
    If `wifi_button` is not switched on during boot, Wi-Fi will be immediately turned
    off.
    """
    log.write("Initializing Wi-Fi", level=log.LogLevel.DEBUG)
    if wifi_button.is_pressed:
        rpi.wifi_switch_on()
    else:
        rpi.wifi_switch_off()


def handle_power_button_off_state():
    """Switches off the system after a 5 second delay."""
    shutdown_delay = 5

    if status.power_button_pressed_time + timedelta(seconds=shutdown_delay) < dt.now():
        if config.DEBUG_MODE_ON:
            log.write("Mock shutting down RPI in debug mode.", log.LogLevel.DEBUG)
        else:
            rpi.shutdown()
        status.power_button_pressed_time = None


def handle_wifi_button_off_state():
    """Switches off the WiFi after config.WIFI_DELAY seconds."""
    if (
        status.wifi_button_pressed_time + timedelta(seconds=config.WIFI_DELAY)
        < dt.now()
    ):
        rpi.wifi_switch_off()
        status.wifi_button_pressed_time = None


if config.USE_BUTTONS:

    log.write("Initalizing Buttons", level=log.LogLevel.DEBUG)

    POWERPIN = 17
    HOURPIN = 27
    WIFIPIN = 22
    LOWBATTERYPIN = 16
    EXTERNALPOWERPIN = 26

    low_battery_button = Button(
        LOWBATTERYPIN, pull_up=True, hold_time=2, hold_repeat=False
    )
    external_power_button = Button(
        EXTERNALPOWERPIN, pull_up=False, hold_time=2, hold_repeat=False
    )
    # Initialise buttons
    power_button = Button(POWERPIN, pull_up=False, hold_time=2, hold_repeat=False)
    hour_button = Button(HOURPIN, pull_up=True, hold_time=2, hold_repeat=False)
    wifi_button = Button(WIFIPIN, pull_up=True, hold_time=2, hold_repeat=False)

    # Register callbacks
    low_battery_button.when_held = _on_low_battery_button_held
    external_power_button.when_released = _on_external_power_button_released
    external_power_button.when_pressed = _on_external_power_button_pressed
    power_button.when_pressed = _on_power_button_pressed
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

    log.write("Buttons initialized", log.LogLevel.DEBUG)

    if not power_button.is_pressed:
        # OTCamera is in an illegal state.
        # The power button should be active for OTCamera to run.
        rpi.shutdown()

    if low_battery_button.is_pressed:
        _on_low_battery_button_held()

    if external_power_button.is_pressed:
        status.external_power_connected = external_power_button.is_pressed
        _on_external_power_button_pressed()


else:
    log.write("No Buttons", log.LogLevel.DEBUG)
