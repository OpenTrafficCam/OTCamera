"""Interactive hardware smoke test for OTCamera on Raspberry Pi."""

import argparse
import logging
import subprocess
import time
from pathlib import Path
from typing import Callable, cast

from OTCamera.bsl.board_provider import BoardComponents, BoardProvider
from OTCamera.config import Config, parse_user_config
from OTCamera.domain.adc import ADCTimeoutError
from OTCamera.domain.camera import Camera, H264Level, H264Profile, VideoFormat
from OTCamera.log import setup_logging
from OTCamera.module.camera.camera_provider import CameraProvider

logger = logging.getLogger(__name__)


class HardwareCheck:
    """Provide interactive checks for camera, LEDs, buttons and ADC."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._board: BoardComponents | None = None
        self._camera: Camera | None = None
        self._test_video_dir = Path("~/test_videos").expanduser().resolve()
        self._led_states: dict[str, str] = {}
        self._button_to_led = {
            "power": "power",
            "wifi": "wifi",
            "hour": "recording",
        }

    def run(self, headless: bool = False) -> None:
        """Start the hardware check loop."""
        setup_logging(self._config)
        self._test_video_dir.mkdir(parents=True, exist_ok=True)
        self._board = BoardProvider.provide(self._config)
        self._camera = CameraProvider.provide(self._config)
        self._register_button_callbacks()
        self._sync_buttons_with_leds()

        close = False
        if not headless:
            self._print_commands()

        try:
            while not close:
                if headless:
                    time.sleep(0.1)
                    continue

                command = input("Enter command: ").strip().lower()
                if command in {"cmd list", "help"}:
                    self._print_commands()
                elif command == "button stat":
                    self._print_button_statuses()
                elif command == "led on":
                    self._turn_leds_on()
                    self._print_led_statuses()
                elif command == "led off":
                    self._turn_leds_off()
                    self._print_led_statuses()
                elif command == "led stat":
                    self._print_led_statuses()
                elif command == "adc stat":
                    self._print_adc_status()
                elif command == "cam on":
                    self._start_recording()
                elif command == "cam off":
                    self._stop_recording()
                elif command == "cam stat":
                    self._print_camera_status()
                elif command == "sh":
                    self._shutdown()
                elif command == "q":
                    close = True
                elif command:
                    print(f"Command '{command}' does not exist.")
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.close()

    def close(self) -> None:
        """Close hardware resources and remove temporary files."""
        if self._camera is not None:
            try:
                self._camera.stop_recording()
            except Exception:
                logger.exception("Failed to stop test recording during cleanup")
            try:
                self._camera.close()
            except Exception:
                logger.exception("Failed to close camera during cleanup")

        if self._board is not None:
            self._board.close()

        if self._test_video_dir.exists():
            for path in self._test_video_dir.iterdir():
                try:
                    path.unlink()
                except IsADirectoryError:
                    logger.warning("Skipping directory in test output path: %s", path)
            try:
                self._test_video_dir.rmdir()
            except OSError:
                logger.debug(
                    "Keeping non-empty test directory: %s", self._test_video_dir
                )

    def _register_button_callbacks(self) -> None:
        assert self._board is not None
        for name, button in self._board.buttons.items():
            button.on_pressed(self._make_button_handler(name, pressed=True))
            button.on_released(self._make_button_handler(name, pressed=False))

    def _make_button_handler(self, name: str, pressed: bool) -> Callable[[], None]:
        def _handler() -> None:
            state = "pressed" if pressed else "released"
            print(f"{name.title()} button {state}")
            led_name = self._button_to_led.get(name)
            if led_name is None:
                return
            if pressed:
                self._set_led_state(led_name, "on")
            else:
                self._set_led_state(led_name, "off")

        return _handler

    def _print_commands(self) -> None:
        print("Commands")
        print("---")
        print("cmd list / help  - List all commands")
        print("button stat      - Show button states")
        print("led on           - Turn on all LEDs")
        print("led off          - Turn off all LEDs")
        print("led stat         - Show last commanded LED states")
        print("adc stat         - Show battery and USB voltages")
        print("cam on           - Start camera recording")
        print("cam off          - Stop camera recording")
        print("cam stat         - Show camera recording status")
        print("sh               - Shutdown the system")
        print("q                - Quit hardware check")

    def _print_button_statuses(self) -> None:
        assert self._board is not None
        print("Button states")
        print("---")
        if not self._board.buttons:
            print("No buttons configured")
            return
        for name, button in self._board.buttons.items():
            print(f"{name}: {button.is_pressed}")

    def _print_led_statuses(self) -> None:
        assert self._board is not None
        print("LED states")
        print("---")
        if not self._board.leds:
            print("No LEDs configured")
            return
        for name in self._board.leds:
            state = self._led_states.get(name, "unknown")
            print(f"{name}: {state}")

    def _print_adc_status(self) -> None:
        assert self._board is not None
        if self._board.adc is None or self._board.adc_config is None:
            print("ADC not configured")
            return

        try:
            usb_voltage = (
                self._board.adc.get_voltage(self._board.adc_config.channel_usb)
                * self._board.adc_config.divider_ratio_usb
            )
            battery_voltage = (
                self._board.adc.get_voltage(self._board.adc_config.channel_battery)
                * self._board.adc_config.divider_ratio_battery
            )
        except ADCTimeoutError:
            print("ADC read timed out")
            return

        print("ADC status")
        print("---")
        print(f"USB voltage: {usb_voltage:.2f} V")
        print(f"Battery voltage: {battery_voltage:.2f} V")

    def _start_recording(self) -> None:
        assert self._camera is not None
        if self._camera.is_recording:
            print("Camera already recording")
            return

        next_index = self._num_videos_recorded() + 1
        output = self._test_video_dir / f"test{next_index}.{self._config.video.format}"
        self._camera.start_recording(
            save_file=str(output),
            video_format=cast(VideoFormat, self._config.video.format),
            resolution=self._config.video.resolution,
            bitrate=self._config.video.h264_bitrate,
            h264_profile=cast(H264Profile, self._config.video.h264_profile),
            h264_level=cast(H264Level, self._config.video.h264_level),
            h264_quality=self._config.video.h264_quality,
        )
        print(f"Started recording to {output}")

    def _stop_recording(self) -> None:
        assert self._camera is not None
        if not self._camera.is_recording:
            print("Camera already stopped")
            return
        self._camera.stop_recording()
        print("Stopped recording")

    def _print_camera_status(self) -> None:
        assert self._camera is not None
        print("Camera status")
        print("---")
        print(f"Recording: {self._camera.is_recording}")
        print(f"Videos recorded in test dir: {self._num_videos_recorded()}")

    def _turn_leds_on(self) -> None:
        assert self._board is not None
        for name in self._board.leds:
            self._set_led_state(name, "on")

    def _turn_leds_off(self) -> None:
        assert self._board is not None
        for name in self._board.leds:
            self._set_led_state(name, "off")

    def _sync_buttons_with_leds(self) -> None:
        assert self._board is not None
        for button_name, led_name in self._button_to_led.items():
            button = self._board.buttons.get(button_name)
            if button is None or led_name not in self._board.leds:
                continue
            self._set_led_state(led_name, "on" if button.is_pressed else "off")

    def _set_led_state(self, led_name: str, state: str) -> None:
        assert self._board is not None
        led = self._board.leds.get(led_name)
        if led is None:
            return
        self._led_states[led_name] = state
        if state == "on":
            led.on()
        elif state == "off":
            led.off()
        elif state == "blink":
            led.blink(background=True)

    def _num_videos_recorded(self) -> int:
        return len([path for path in self._test_video_dir.iterdir() if path.is_file()])

    def _shutdown(self) -> None:
        print("System shutdown requested")
        self._turn_leds_off()
        if not self._config.debug_mode_on:
            logging.shutdown()
            subprocess.call(["sudo", "shutdown", "-h", "now"])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="~/user_config.yaml",
        help="Absolute or relative path to the user config file.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without interactive prompts.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the OTCamera hardware check tool."""
    args = _parse_args()
    config = parse_user_config(args.config)
    checker = HardwareCheck(config)
    checker.run(headless=args.headless)


if __name__ == "__main__":
    main()
