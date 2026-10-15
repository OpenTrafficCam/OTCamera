import sys
from dataclasses import replace
from types import ModuleType
from typing import Any, cast

import pytest

from OTCamera.bsl.board_provider import (
    BoardComponents,
    BoardProvider,
    load_board_definition,
)
from OTCamera.bsl.boards.v20d import BoardV20d
from OTCamera.config import Config


class FakeCloseable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeLed(FakeCloseable):
    instances: list["FakeLed"] = []

    def __init__(self, pin: int) -> None:
        super().__init__()
        self.pin = pin
        self.off_calls = 0
        self.__class__.instances.append(self)

    def off(self) -> None:
        self.off_calls += 1


class FakeButton(FakeCloseable):
    instances: list["FakeButton"] = []

    def __init__(
        self,
        pin: int,
        bounce_time: float = 0.05,
        pull_up: bool | None = True,
        hold_time: float = 2.0,
        hold_repeat: bool = False,
        active_state: bool | None = None,
    ) -> None:
        super().__init__()
        self.pin = pin
        self.bounce_time = bounce_time
        self.pull_up = pull_up
        self.active_state = active_state
        self.hold_time = hold_time
        self.hold_repeat = hold_repeat
        self.when_pressed = None
        self.when_held = None
        self.when_released = None
        self.__class__.instances.append(self)

    @property
    def is_pressed(self) -> bool:
        return False


class FakeAdc(FakeCloseable):
    instances: list["FakeAdc"] = []

    def __init__(self, i2c_address: int, fsr: float, i2c_bus: int = 1) -> None:
        super().__init__()
        self.i2c_address = i2c_address
        self.fsr = fsr
        self.i2c_bus = i2c_bus
        self.__class__.instances.append(self)


class FailingAdc(FakeCloseable):
    def __init__(self, i2c_address: int, fsr: float, i2c_bus: int = 1) -> None:
        super().__init__()
        raise RuntimeError("adc init failed")


def _make_config(
    pcb_version: str = "v2",
    use_leds: bool = False,
    use_buttons: bool = False,
    use_adc: bool = False,
) -> Config:
    config = Config()
    config.hardware.pcb_version = pcb_version
    config.hardware.use_leds = use_leds
    config.hardware.use_buttons = use_buttons
    config.hardware.use_adc = use_adc
    return config


def _install_fake_gpiozero(monkeypatch: pytest.MonkeyPatch) -> None:
    gpiozero_module: Any = ModuleType("gpiozero")

    class FakeDevice:
        pin_factory = None

    gpiozero_module.Device = FakeDevice

    pins_module: Any = ModuleType("gpiozero.pins")
    lgpio_module: Any = ModuleType("gpiozero.pins.lgpio")

    class FakeLGPIOFactory:
        pass

    lgpio_module.LGPIOFactory = FakeLGPIOFactory
    pins_module.lgpio = lgpio_module
    gpiozero_module.pins = pins_module

    monkeypatch.setitem(sys.modules, "gpiozero", gpiozero_module)
    monkeypatch.setitem(sys.modules, "gpiozero.pins", pins_module)
    monkeypatch.setitem(sys.modules, "gpiozero.pins.lgpio", lgpio_module)


class TestLoadBoardDefinition:
    def test_unknown_pcb_version_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown PCB version"):
            load_board_definition("v99")

    def test_v2_loads(self) -> None:
        board = load_board_definition("v2")
        assert board.led_power_pin >= 0

    def test_v2_has_correct_adc_address(self) -> None:
        board = load_board_definition("v2")
        assert board.adc_i2c_address == 0x48

    def test_v16b_is_an_alias_for_v2(self) -> None:
        assert type(load_board_definition("v16b")) is type(load_board_definition("v2"))

    def test_v20d_loads(self) -> None:
        board = load_board_definition("v20d")
        assert board.adc_i2c_bus == 3
        assert board.button_light_pin == 16


class TestBoardComponents:
    def test_close_with_empty_dicts(self) -> None:
        bc = BoardComponents(leds={}, buttons={}, adc=None, adc_config=None)
        bc.close()

    def test_close_continues_on_errors(self) -> None:
        class FailingCloseable(FakeCloseable):
            def close(self) -> None:
                self.closed = True
                raise RuntimeError("boom")

        led = FakeCloseable()
        button = FailingCloseable()
        adc = FakeCloseable()
        bc = BoardComponents(
            leds={"power": cast(Any, led)},
            buttons={"wifi": cast(Any, button)},
            adc=cast(Any, adc),
            adc_config=None,
        )
        bc.close()
        assert led.closed
        assert button.closed
        assert adc.closed


class TestBoardProvider:
    def test_provide_cleans_up_on_partial_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_gpiozero(monkeypatch)
        FakeLed.instances = []
        FakeButton.instances = []
        FakeAdc.instances = []

        monkeypatch.setattr("OTCamera.bsl.led.pwm_led.PwmLed", FakeLed)
        monkeypatch.setattr("OTCamera.bsl.button.gpio_button.GpioButton", FakeButton)
        monkeypatch.setattr("OTCamera.bsl.adc.tla2024.TLA2024", FailingAdc)

        config = _make_config(use_leds=True, use_buttons=True, use_adc=True)

        with pytest.raises(RuntimeError, match="adc init failed"):
            BoardProvider.provide(config)

        assert all(led.closed for led in FakeLed.instances)
        assert all(button.closed for button in FakeButton.instances)

    def test_provide_with_features_disabled_returns_empty_components(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_gpiozero(monkeypatch)
        config = _make_config()

        components = BoardProvider.provide(config)

        assert components.leds == {}
        assert components.buttons == {}
        assert components.adc is None
        assert components.adc_config is None


class TestBoardProviderPerRevision:
    """The provider must pass each revision's own values through unchanged."""

    def _provide(
        self, monkeypatch: pytest.MonkeyPatch, pcb_version: str
    ) -> BoardComponents:
        _install_fake_gpiozero(monkeypatch)
        FakeLed.instances = []
        FakeButton.instances = []
        FakeAdc.instances = []

        monkeypatch.setattr("OTCamera.bsl.led.pwm_led.PwmLed", FakeLed)
        monkeypatch.setattr("OTCamera.bsl.button.gpio_button.GpioButton", FakeButton)
        monkeypatch.setattr("OTCamera.bsl.adc.tla2024.TLA2024", FakeAdc)

        config = _make_config(
            pcb_version=pcb_version,
            use_leds=True,
            use_buttons=True,
            use_adc=True,
        )
        return BoardProvider.provide(config)

    def test_v2_keeps_three_leds_and_three_buttons(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        components = self._provide(monkeypatch, "v2")

        assert sorted(components.leds) == ["power", "recording", "wifi"]
        assert sorted(components.buttons) == ["hour", "power", "wifi"]

    def test_v2_uses_the_hardware_i2c_bus(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._provide(monkeypatch, "v2")

        assert FakeAdc.instances[0].i2c_bus == 1

    def test_v2_lets_gpiozero_pull_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._provide(monkeypatch, "v2")

        assert all(button.pull_up is True for button in FakeButton.instances)
        assert all(button.active_state is None for button in FakeButton.instances)

    def test_v20d_adds_the_intrusion_led_and_the_light_switch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        components = self._provide(monkeypatch, "v20d")

        assert sorted(components.leds) == ["intrusion", "power", "recording", "wifi"]
        assert sorted(components.buttons) == ["hour", "light", "power", "wifi"]
        assert components.leds["intrusion"].pin == 7  # type: ignore[attr-defined]

    def test_v20d_uses_the_bit_banged_i2c_bus(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._provide(monkeypatch, "v20d")

        assert FakeAdc.instances[0].i2c_bus == 3

    def test_v20d_leaves_the_pull_to_config_txt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._provide(monkeypatch, "v20d")

        assert all(button.pull_up is None for button in FakeButton.instances)
        assert all(button.active_state is True for button in FakeButton.instances)

    @pytest.mark.parametrize("name", ["power", "hour", "wifi", "light"])
    def test_each_switch_can_invert_its_active_state(
        self, monkeypatch: pytest.MonkeyPatch, name: str
    ) -> None:
        board = replace(BoardV20d(), **{f"button_{name}_active_state": False})
        monkeypatch.setattr(
            "OTCamera.bsl.board_provider.load_board_definition", lambda _: board
        )

        self._provide(monkeypatch, "v20d")

        inverted_pin = getattr(board, f"button_{name}_pin")
        assert len(FakeButton.instances) == 4
        for button in FakeButton.instances:
            assert button.pull_up is None
            assert button.active_state is (button.pin != inverted_pin)

    @pytest.mark.parametrize("pcb_version", ["v2", "v20d"])
    def test_the_led_enable_pin_is_never_claimed(
        self, monkeypatch: pytest.MonkeyPatch, pcb_version: str
    ) -> None:
        self._provide(monkeypatch, pcb_version)

        assert 10 not in [led.pin for led in FakeLed.instances]
        assert 10 not in [button.pin for button in FakeButton.instances]
