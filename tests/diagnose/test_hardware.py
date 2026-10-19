"""Resource ownership, board polarity and final LED-enable state."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from OTCamera.bsl.board_provider import load_board_definition
from OTCamera.bsl.button import gpio_button
from OTCamera.diagnose import hardware as h


@pytest.mark.parametrize("partial", [False, True])
def test_gpio_factory_polarity_and_cleanup_order(
    partial: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    previous = object()
    device = SimpleNamespace(pin_factory=previous)
    factory = Mock()
    button = Mock()
    output_device = Mock()
    events: list[str] = []
    button.close.side_effect = lambda: events.append("button")
    factory.close.side_effect = lambda: events.append("factory")
    output_device.close.side_effect = lambda: events.append("output")
    build = Mock(return_value=button)
    if partial:
        build.side_effect = [button, OSError("busy")]
    monkeypatch.setattr(gpio_button, "GpioButton", build)
    monkeypatch.setitem(
        sys.modules,
        "gpiozero",
        SimpleNamespace(Device=device, OutputDevice=Mock(return_value=output_device)),
    )
    monkeypatch.setitem(
        sys.modules,
        "gpiozero.pins.lgpio",
        SimpleNamespace(LGPIOFactory=Mock(return_value=factory)),
    )
    latch = Mock(side_effect=lambda args: events.append("latch"))
    monkeypatch.setattr(h, "output", latch)
    board = load_board_definition("v20d")
    hardware = h.Hardware(board)
    if partial:
        with pytest.raises(OSError, match="busy"):
            hardware.open_gpio()
    else:
        hardware.open_gpio()
        assert len(hardware.buttons) == len(hardware.leds) == 4
        assert (
            build.call_args_list[0].kwargs["active_state"]
            == board.button_power_active_state
        )
        assert build.call_args_list[0].kwargs["pull_up"] == board.button_power_pull_up
    assert device.pin_factory is factory
    hardware.close()
    assert device.pin_factory is previous
    assert events[-3:] == ["factory", "latch", "latch"]
    assert [c.args[0] for c in latch.call_args_list] == [
        ["pinctrl", "set", str(board.led_enable_pin), "op", "dh"],
        ["pinctrl", "set", str(board.led_power_pin), "op", "dh"],
    ]
    assert not hardware.cleanup_errors


def test_close_continues_after_release_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    hardware = h.Hardware(load_board_definition("v20d"))
    first, second = Mock(), Mock()
    first.close.side_effect = RuntimeError("cannot close")
    hardware._keep(second)
    hardware._keep(first)
    hardware.gpio_touched = True
    latch = Mock(side_effect=RuntimeError("cannot latch"))
    monkeypatch.setattr(h, "output", latch)
    hardware.close()
    second.close.assert_called_once()
    assert len(hardware.cleanup_errors) == 3
    assert latch.call_count == 2


def test_adc_is_reused_and_closed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    adc = Mock()
    build = Mock(return_value=adc)
    monkeypatch.setitem(
        sys.modules, "OTCamera.bsl.adc.tla2024", SimpleNamespace(TLA2024=build)
    )
    hardware = h.Hardware(load_board_definition("v20d"))
    hardware.open_adc()
    hardware.open_adc()
    build.assert_called_once()
    hardware.close()
    adc.close.assert_called_once()


def test_dark_lowers_outputs_before_enable() -> None:
    hardware = h.Hardware(load_board_definition("v20d"))
    calls = Mock()
    hardware.leds = [calls.led1, calls.led2]
    hardware.enable = calls.enable
    hardware.dark()
    assert calls.mock_calls == [call.led1.off(), call.led2.off(), call.enable.on()]
