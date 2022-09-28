from gpiozero import Button
from gpiozero import PWMLED

from picamerax import PiCamera
from subprocess import call
from pathlib import Path

# Button GPIO Pins
BUTTON_POWER_PIN = 17
BUTTON_HOUR_PIN = 27
BUTTON_WIFI_PIN = 22
LOWBATTERY_PIN = 16
EXTERNAL_POWER_PIN = 26

# Camera
camera = PiCamera()
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


def surround_with_dashes(func):
    def wrapper_func(*args, **kwargs):
        print("---")
        func(*args, **kwargs)
        print("---")

    return wrapper_func


# Callbacks
@surround_with_dashes
def on_power_button_pressed():
    print(f"Power button is on: {power_button.is_pressed}")
    power_led.on()
    print(f"Power LED is on: {power_led.is_active}")


@surround_with_dashes
def on_power_button_released():
    print(f"Power button is off: {not power_button.is_pressed}")
    power_led.off()
    print(f"Power LED is off: {not power_led.is_active}")


@surround_with_dashes
def on_wifi_button_pressed():
    print(f"Wifi button is on: {wifi_button.is_pressed}")
    wifi_led.on()
    print(f"Wifi LED is on: {wifi_led.is_active}")


@surround_with_dashes
def on_wifi_button_released():
    print(f"Wifi button is off: {not wifi_button.is_pressed}")
    wifi_led.off()
    print(f"Wifi LED is off: {not wifi_led.is_active}")


@surround_with_dashes
def on_hour_button_pressed():
    print(f"Hour button is on: {hour_button.is_pressed}")
    hour_led.on()
    print(f"Hour LED is on: {power_led.is_active}")


@surround_with_dashes
def on_hour_button_released():
    print(f"Hour button is off: {not hour_button.is_pressed}")
    hour_led.off()
    print(f"Hour LED is off: {not hour_led.is_active}")


# Handlers
power_button.when_pressed = on_power_button_pressed
power_button.when_released = on_power_button_released
wifi_button.when_pressed = on_wifi_button_pressed
wifi_button.when_released = on_wifi_button_released
hour_button.when_pressed = on_hour_button_pressed
hour_button.when_released = on_hour_button_released


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


def main():
    print("Test OTCamera Hardware")

    sync_button_with_led(power_button, power_led)
    sync_button_with_led(wifi_button, wifi_led)
    sync_button_with_led(hour_button, hour_led)

    close: bool = False

    while not close:
        print("Enter command: ")
        user_input = input()
        sanitized_input = sanitize(user_input)

        if sanitized_input == "button stat":
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
            call("sudo shutdown -h now", shell=True)
        elif sanitized_input == "q":
            close = True
            print("Quit app.")
        else:
            print(f"Command '{sanitized_input}' does not exist!")


if __name__ == "__main__":
    main()
