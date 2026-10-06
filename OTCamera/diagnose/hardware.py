"""Persistent board resources for an inspection, with explicit cleanup."""

from contextlib import ExitStack
from typing import Any

from OTCamera.bsl.boards.board import Board
from OTCamera.diagnose.report import Check, output
from OTCamera.domain.adc import ADC
from OTCamera.domain.button import Button

SWITCHES = ("power", "wifi", "hour", "light")
LED_NAMES = ("power", "wifi", "rec", "intrusion")


class Hardware:
    """Keep acquired GPIOs and ADC open until the inspection releases them."""

    def __init__(self, board: Board) -> None:
        self.board = board
        self.resources = ExitStack()
        self.buttons: dict[str, Button] = {}
        self.leds: list[Any] = []
        self.enable: Any = None
        self.adc: ADC | None = None
        self.gpio_touched = False
        self.cleanup_errors: list[str] = []

    def _keep(self, resource: Any) -> Any:
        self.resources.callback(self._release, resource)
        return resource

    def _release(self, resource: Any) -> None:
        try:
            resource.close()
        except Exception as exc:
            self.cleanup_errors.append(str(exc))

    def open_adc(self) -> None:
        """Acquire the board-selected application ADC once."""
        if self.adc is None:
            from OTCamera.bsl.adc.tla2024 import TLA2024

            self.adc = self._keep(
                TLA2024(
                    self.board.adc_i2c_address,
                    self.board.adc_fsr,
                    self.board.adc_i2c_bus,
                )
            )

    def voltages(self) -> tuple[float, float]:
        """Read scaled external supply and battery voltages."""
        if self.adc is None:
            raise RuntimeError("ADC unavailable")
        return (
            self.adc.get_voltage(self.board.adc_channel_usb)
            * self.board.adc_divider_ratio_usb,
            self.adc.get_voltage(self.board.adc_channel_battery)
            * self.board.adc_divider_ratio_battery,
        )

    def open_gpio(self) -> None:
        """Acquire switches using application polarity contracts and raw LED outputs."""
        from gpiozero import Device, OutputDevice
        from gpiozero.pins.lgpio import LGPIOFactory

        from OTCamera.bsl.button.gpio_button import GpioButton

        factory = self._keep(LGPIOFactory())
        self.resources.callback(setattr, Device, "pin_factory", Device.pin_factory)
        Device.pin_factory = factory
        self.gpio_touched = True
        for name in SWITCHES:
            self.buttons[name] = self._keep(
                GpioButton(
                    getattr(self.board, f"button_{name}_pin"),
                    bounce_time=self.board.button_bounce_time,
                    pull_up=getattr(self.board, f"button_{name}_pull_up"),
                    active_state=getattr(self.board, f"button_{name}_active_state"),
                    hold_time=self.board.button_hold_time,
                )
            )
        for name in LED_NAMES:
            self.leds.append(
                self._keep(
                    OutputDevice(
                        getattr(self.board, f"led_{name}_pin"),
                        initial_value=False,
                        pin_factory=factory,
                    )
                )
            )
        self.enable = self._keep(
            OutputDevice(
                self.board.led_enable_pin,
                initial_value=True,
                pin_factory=factory,
            )
        )

    def switches(self) -> tuple[bool, ...]:
        """Read logical ON/OFF, including REC on the hour input."""
        return tuple(self.buttons[name].is_pressed for name in SWITCHES)

    def lights(self, slot: int | None = None) -> None:
        """Keep at most the selected LED output high."""
        for led in self.leds:
            led.off()
        if slot is not None:
            self.leds[slot].on()

    def dark(self) -> None:
        """Set outputs low before restoring enable high, avoiding a flash."""
        self.lights()
        self.enable.on()

    def close(self) -> None:
        """Release everything, then explicitly set LED enable and PWR high."""
        self.resources.close()
        if not self.gpio_touched:
            return
        for name, pin in (
            ("LED enable", self.board.led_enable_pin),
            ("LED PWR", self.board.led_power_pin),
        ):
            if pin is None:
                continue
            try:
                output(["pinctrl", "set", str(pin), "op", "dh"])
            except Exception as exc:
                self.cleanup_errors.append(f"{name} restore: {exc}")


def adc_check(hardware: Hardware, low_battery: float) -> Check:
    """Measure both supplies and check the configured minimum battery voltage."""
    try:
        hardware.open_adc()
        external, battery = hardware.voltages()
        return Check(
            "i2c.tla2024",
            battery >= low_battery,
            "Both supplies measured; battery above low-battery threshold"
            if battery >= low_battery
            else f"Battery {battery:.2f} V below {low_battery:.2f} V",
            {
                "usb_voltage_v": external,
                "battery_voltage_v": battery,
            },
        )
    except Exception as exc:
        return Check("i2c.tla2024", False, str(exc))
