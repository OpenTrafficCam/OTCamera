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

import argparse
import time
from pathlib import Path
from subprocess import call
from typing import Any, Callable, TypeVar

from gpiozero import PWMLED, Button
from picamerax import PiCamera

# Button GPIO Pins
BUTTON_POWER_PIN = 17
BUTTON_HOUR_PIN = 27
BUTTON_WIFI_PIN = 22
LOWBATTERY_PIN = 16
EXTERNAL_POWER_PIN = 26

# Camera
camera = PiCamera()
test_video_dir = Path("~/test_videos").expanduser().resolve()
test_video_dir.mkdir(parents=True, exist_ok=True)


# Initialise buttons
low_battery_button = Button(
    LOWBATTERY_PIN, pull_up=True, hold_time=2, hold_repeat=False
)
external_power_button = Button(
    EXTERNAL_POWER_PIN, pull_up=False, hold_time=2, hold_repeat=False
)
power_button = Button(BUTTON_POWER_PIN, pull_up=False, hold_time=2, hold_repeat=False)
hour_button = Button(BUTTON_HOUR_PIN, pull_up=True, hold_time=2, hold_repeat=False)
wifi_button = Button(BUTTON_WIFI_PIN, pull_up=True, hold_time=2, hold_repeat=False)

# LED GPIO Pins
LED_POWER_PIN = 13
LED_WIFI_PIN = 12
LED_REC_PIN = 6
power_led = PWMLED(LED_POWER_PIN)
wifi_led = PWMLED(LED_WIFI_PIN)
hour_led = PWMLED(LED_REC_PIN)


F = TypeVar("F", bound=Callable[..., Any])


def surround_with_dashes(func: F) -> F:
    def wrapper_func(*args: Any, **kwargs: Any) -> Any:
        print("---")
        func(*args, **kwargs)
        print("---")

    return wrapper_func  # type: ignore


# Callbacks
@surround_with_dashes
def on_power_button_pressed() -> None:
    print("Power button pressed")
    print(f"Power button is on: {power_button.is_pressed}")
    power_led.on()
    print(f"Power LED is on: {power_led.is_active}")


@surround_with_dashes
def on_power_button_released() -> None:
    print("Power button released")
    print(f"Power button is on: {power_button.is_pressed}")
    power_led.off()
    print(f"Power LED is on: {power_led.is_active}")


@surround_with_dashes
def on_wifi_button_pressed() -> None:
    print("Wifi button pressed")
    print(f"Wifi button is on: {wifi_button.is_pressed}")
    wifi_led.on()
    print(f"Wifi LED is on: {wifi_led.is_active}")


@surround_with_dashes
def on_wifi_button_released() -> None:
    print("Wifi button released")
    print(f"Wifi button is on: {wifi_button.is_pressed}")
    wifi_led.off()
    print(f"Wifi LED is on: {wifi_led.is_active}")


@surround_with_dashes
def on_hour_button_pressed() -> None:
    print("Hour button pressed")
    print(f"Hour button is on: {hour_button.is_pressed}")
    hour_led.on()
    print(f"Hour LED is on: {power_led.is_active}")


@surround_with_dashes
def on_hour_button_released() -> None:
    print("Hour button released")
    print(f"Hour button is on: {hour_button.is_pressed}")
    hour_led.off()
    print(f"Hour LED is on: {hour_led.is_active}")


@surround_with_dashes
def on_external_power_button_pressed() -> None:
    print("External power is connected")
    power_led.blink(n=3, on_time=0.25, off_time=0.25)
    hour_led.blink(n=3, on_time=0.25, off_time=0.25)
    wifi_led.blink(n=3, on_time=0.25, off_time=0.25, background=False)
    sync_all_buttons_with_led()

    print(f"External power is connected: {external_power_button.is_pressed}")


@surround_with_dashes
def on_external_power_button_released() -> None:
    print("External power is not connected")
    power_led.blink(n=2, on_time=0.25, off_time=0.25)
    hour_led.blink(n=2, on_time=0.25, off_time=0.25)
    wifi_led.blink(n=2, on_time=0.25, off_time=0.25, background=False)
    sync_all_buttons_with_led()
    print(f"External power is connected: {external_power_button.is_pressed}")


# Handlers
power_button.when_pressed = on_power_button_pressed
power_button.when_released = on_power_button_released
wifi_button.when_pressed = on_wifi_button_pressed
wifi_button.when_released = on_wifi_button_released
hour_button.when_pressed = on_hour_button_pressed
hour_button.when_released = on_hour_button_released
external_power_button.when_pressed = on_external_power_button_pressed
external_power_button.when_released = on_external_power_button_released


def sanitize(input: str) -> str:
    return input.strip().lower()


@surround_with_dashes
def print_led_statuses() -> None:
    print("LED statuses")
    print("---")
    print(f"Power LED active: {power_led.is_active}")
    print(f"Wifi LED active: {wifi_led.is_active}")
    print(f"Hour LED active: {hour_led.is_active}")


@surround_with_dashes
def print_button_statuses() -> None:
    print("Button statuses")
    print("---")
    print(f"Power Button active: {power_button.is_active}")
    print(f"Wifi Button active: {wifi_button.is_active}")
    print(f"Hour Button active: {hour_button.is_active}")
    print(f"Low Battery active: {low_battery_button.is_active}")
    print(f"External Power Pin active: {external_power_button.is_active}")


@surround_with_dashes
def print_cmd_list() -> None:
    print("Commands")
    print("---")
    print("cmd list - List all commands.")
    print("help - List all commands.")
    print("---")
    print("button stat - Show status of all buttons.")
    print("---")
    print("led on - Turn on all LEDs.")
    print("led off - Turn off all LEDs.")
    print("led stat - Show status of all LEDs.")
    print("---")
    print("cam on - Start camera recording.")
    print("cam off - Stop camera recording.")
    print("cam stat - Show number of recorded videos.")
    print("---")
    print("sh - System shutdown.")
    print("q - Quit application.")


def turn_leds_on() -> None:
    power_led.on()
    wifi_led.on()
    hour_led.on()


def turn_leds_off() -> None:
    power_led.off()
    wifi_led.off()
    hour_led.off()


def sync_button_with_led(button: Button, led: PWMLED) -> None:
    if button.is_active:
        led.on()
    else:
        led.off()


def sync_all_buttons_with_led() -> None:
    sync_button_with_led(power_button, power_led)
    sync_button_with_led(wifi_button, wifi_led)
    sync_button_with_led(hour_button, hour_led)


def get_num_videos_recorded() -> int:
    return len([f for f in test_video_dir.iterdir()])


@surround_with_dashes
def print_num_videos_recorded() -> None:
    print(f"Num videos recorded: {get_num_videos_recorded()}")


@surround_with_dashes
def start_recording() -> None:
    if not camera.recording:
        camera.start_recording(
            output=str(test_video_dir / f"test{get_num_videos_recorded() + 1}.h264")
        )
        print("Start camera recording.")
    else:
        print("Camera already recording.")
    print(f"Camera recording: {camera.recording}")


@surround_with_dashes
def stop_recording() -> None:
    if camera.recording:
        camera.stop_recording()
        print("Stop camera recording.")
    else:
        print("Camera recording already stopped.")
    print(f"Camera recording: {camera.recording}")


@surround_with_dashes
def teardown() -> None:
    print("Execute teardown.")
    print("---")
    if camera.recording:
        camera.stop_recording()
    camera.close()
    print("Camera closed.")

    for f in test_video_dir.iterdir():
        f.unlink()
    test_video_dir.rmdir()
    print("Test directory removed")


def start_app(headless: bool = False) -> None:
    print("Test OTCamera Hardware")

    sync_all_buttons_with_led()

    close: bool = False
    if not headless:
        print_cmd_list()
    try:
        while not close:
            if not headless:
                print("Enter command: ")
                user_input = input()
                sanitized_input = sanitize(user_input)

                if sanitized_input == "cmd list" or sanitized_input == "help":
                    print_cmd_list()
                elif sanitized_input == "button stat":
                    print_button_statuses()
                elif sanitized_input == "led stat":
                    print_led_statuses()
                elif sanitized_input == "cam stat":
                    print_num_videos_recorded()
                elif sanitized_input == "led on":
                    turn_leds_on()
                    print_led_statuses()
                elif sanitized_input == "led off":
                    turn_leds_off()
                    print_led_statuses()
                elif sanitized_input == "cam on":
                    start_recording()
                elif sanitized_input == "cam off":
                    stop_recording()
                elif sanitized_input == "sh":
                    teardown()
                    call("sudo shutdown -h now", shell=True)
                elif sanitized_input == "q":
                    close = True
                else:
                    print(f"Command '{sanitized_input}' does not exist!")
            else:
                time.sleep(0.1)
    except KeyboardInterrupt:
        close = True

    teardown()
    print("Quit app.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--headless",
        action="store_true",
        help="OTCamera hardware test will be run in headless mode.",
    )
    args = parser.parse_args()

    return args


def main() -> None:
    args = parse_args()
    start_app(headless=args.headless)


if __name__ == "__main__":
    main()
