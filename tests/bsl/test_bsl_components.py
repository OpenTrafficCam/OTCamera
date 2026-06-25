import sys
from types import ModuleType
from typing import Any, cast

import pytest

from OTCamera.bsl.adc.tla2024 import TLA2024
from OTCamera.bsl.button.gpio_button import GpioButton
from OTCamera.bsl.led.pwm_led import PwmLed


class FakePWMLED:
    def __init__(self, pin: int) -> None:
        self.pin = pin
        self.calls: list[tuple[object, ...]] = []
        self.is_pressed = False

    def on(self) -> None:
        self.calls.append(("on",))

    def off(self) -> None:
        self.calls.append(("off",))

    def blink(self, **kwargs: object) -> None:
        self.calls.append(("blink", kwargs))

    def pulse(self, **kwargs: object) -> None:
        self.calls.append(("pulse", kwargs))

    def close(self) -> None:
        self.calls.append(("close",))


class FakeGpioZeroButton:
    def __init__(
        self,
        pin: int,
        pull_up: bool = True,
        hold_time: float = 2.0,
        hold_repeat: bool = False,
        bounce_time: float | None = None,
    ) -> None:
        self.pin = pin
        self.pull_up = pull_up
        self.hold_time = hold_time
        self.hold_repeat = hold_repeat
        self.bounce_time = bounce_time
        self.when_pressed = None
        self.when_held = None
        self.when_released = None
        self.is_pressed = False
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeSMBus:
    def __init__(self, bus_number: int) -> None:
        self.bus_number = bus_number
        self.write_calls: list[tuple[int, int, object]] = []
        self.read_calls = 0
        self.closed = False

    def write_i2c_block_data(self, address: int, register: int, data: object) -> None:
        self.write_calls.append((address, register, data))

    def read_i2c_block_data(
        self,
        address: int,
        register: int,
        length: int,
    ) -> list[int]:
        self.read_calls += 1
        if register == 0x01:
            return [0x80, 0x00]
        return [0x40, 0x00]

    def close(self) -> None:
        self.closed = True


def _install_fake_gpiozero(monkeypatch: pytest.MonkeyPatch) -> None:
    module: Any = ModuleType("gpiozero")
    module.PWMLED = FakePWMLED
    module.Button = FakeGpioZeroButton
    monkeypatch.setitem(sys.modules, "gpiozero", module)


def _install_fake_smbus2(monkeypatch: pytest.MonkeyPatch) -> None:
    module: Any = ModuleType("smbus2")
    module.SMBus = FakeSMBus
    monkeypatch.setitem(sys.modules, "smbus2", module)


class TestPwmLed:
    def test_delegates_to_pwmled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_gpiozero(monkeypatch)

        led = PwmLed(11)
        led.on()
        led.blink(on_time=0.2, off_time=0.3, n=2)
        led.pulse(fade_in_time=0.4, fade_out_time=0.5, n=3)
        led.close()

        assert led._led.pin == 11
        assert led._led.calls == [
            ("on",),
            ("off",),
            ("blink", {"on_time": 0.2, "off_time": 0.3, "n": 2, "background": True}),
            ("off",),
            (
                "pulse",
                {
                    "fade_in_time": 0.4,
                    "fade_out_time": 0.5,
                    "n": 3,
                    "background": True,
                },
            ),
            ("close",),
        ]


class TestGpioButton:
    def test_delegates_to_gpiozero_button(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_gpiozero(monkeypatch)

        button = GpioButton(19, bounce_time=0.05, pull_up=False, hold_time=1.5)
        pressed: list[str] = []
        held: list[str] = []
        released: list[str] = []
        button.on_pressed(lambda: pressed.append("pressed"))
        button.on_held(lambda: held.append("held"))
        button.on_released(lambda: released.append("released"))

        assert not button.is_pressed
        button._button.when_pressed()
        button._button.when_held()
        button._button.when_released()
        button.close()

        assert button._button.pin == 19
        assert button._button.pull_up is False
        assert button._button.hold_time == 1.5
        assert button._button.bounce_time == 0.05
        assert pressed == ["pressed"]
        assert held == ["held"]
        assert released == ["released"]
        assert button._button.closed


class TestTLA2024:
    def test_reads_voltage_and_closes_bus(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_smbus2(monkeypatch)

        adc = TLA2024()
        voltage = adc.get_voltage(0)
        adc.close()

        fake_bus = cast(FakeSMBus, adc._bus)
        assert adc.channels == 4
        assert pytest.approx(voltage, rel=1e-6) == 2.048
        assert fake_bus.closed
        assert fake_bus.write_calls[0][0] == 0x48
