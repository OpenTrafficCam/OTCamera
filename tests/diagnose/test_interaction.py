"""Exercise timed physical sequences without real sleeps or GPIO."""

from typing import Any
from unittest.mock import Mock

import pytest

from OTCamera.config import Config
from OTCamera.diagnose import interaction as m
from OTCamera.diagnose.hardware import Hardware


class Clock:
    def __init__(self) -> None:
        self.time = 0.0

    def now(self) -> float:
        return self.time

    def sleep(self, duration: float) -> None:
        self.time += duration


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    value = Clock()
    monkeypatch.setattr(m, "monotonic", value.now)
    monkeypatch.setattr(m, "sleep", value.sleep)
    return value


@pytest.mark.parametrize(
    "fitted,failure",
    [
        (fitted, failure)
        for fitted in ([], ["REC"], ["WIFI", "PWR"], ["PWR", "WIFI", "REC", "LIGHT"])
        for failure in [None, *range((len(fitted) + 1 if fitted else 0) + 2)]
    ],
)
@pytest.mark.parametrize("mode", ["reject", "timeout", "no"])
def test_ui_stops_at_first_failure_and_restores_leds(
    fitted: list[str],
    failure: int | None,
    mode: str,
    clock: Clock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hardware = Mock(spec=Hardware)
    hardware.enable = Mock()
    hardware.leds = [Mock() for _ in range(4)]
    terminal = Mock(spec=m.Terminal)
    phase, entered, boundary = -1, 0.0, 0
    names = [name for name in m.SWITCHES if name in fitted]
    visual_start = len(names) + 1 if names else 0
    states: tuple[bool, ...] = (False,) * len(names)

    def flush() -> None:
        nonlocal phase, entered, boundary
        if boundary % 2 == 0:
            phase += 1
            entered = clock.now()
        boundary += 1

    def switches() -> tuple[bool, ...]:
        nonlocal states
        if phase != failure and clock.now() - entered >= 0.3:
            states = tuple(i >= phase for i in range(len(names)))
        return states

    def key() -> str:
        if phase == failure:
            if mode == "timeout":
                return ""
            return "n" if mode == "no" and phase >= visual_start else "x"
        return "y" if phase >= visual_start and clock.now() - entered >= 0.3 else ""

    def lights(slot: int | None = None) -> None:
        # No LED animation until the switches have been tested.
        assert phase >= visual_start or slot == 0

    terminal.flush.side_effect = flush
    terminal.key.side_effect = key
    hardware.switches.side_effect = switches
    hardware.lights.side_effect = lights
    result = m.ui(hardware, terminal, fitted)
    assert result.ok == (failure is None)
    assert phase == (visual_start + 1 if failure is None else failure)
    assert result.measured == {"fitted_switches": names}
    hardware.open_gpio.assert_called_once_with(fitted)
    hardware.dark.assert_called_once()
    hardware.lights.assert_called_with(0)
    hardware.enable.on.assert_called_once()
    text = capsys.readouterr().out
    assert "[##############################] 30 s" in text
    if failure == 0 and mode == "timeout":
        assert "[##########--------------------] 10 s" in text
    if failure is not None:
        assert ("timeout" if mode == "timeout" else "rejected") in result.detail
        assert clock.now() < m.STAGE_SECONDS + 10
    else:
        for name in names:
            assert f"Switch {name}_Button OFF" in text
        for name in set(m.SWITCHES) - set(names):
            assert f"{name}_Button" not in text
        assert ("Switch all buttons ON" in text) == bool(names)
        assert "Are ALL LEDs OFF?" in text
        assert "YES: Press Y." in text
        assert states == (False,) * len(names)
        hardware.enable.off.assert_called_once()
        assert all(led.on.call_count == 1 for led in hardware.leds)


def test_unexpected_switch_stops_stage(clock: Clock) -> None:
    terminal = Mock(spec=m.Terminal)
    terminal.rejected.return_value = False
    terminal.key.return_value = ""
    reason = m.stage(
        terminal,
        "WIFI",
        "Switch WIFI_Button ON",
        lambda: (False, True),
        lambda s: all(s),
        0.2,
        lambda: None,
        lambda s: not s[0],
    )
    assert reason and "unexpected" in reason
    assert clock.now() < 1


def test_contact_bounce_does_not_confirm(clock: Clock) -> None:
    terminal = Mock(spec=m.Terminal)
    terminal.rejected.return_value = False
    terminal.key.return_value = ""
    reason = m.stage(
        terminal,
        "PWR",
        "Switch PWR_Button ON",
        lambda: clock.now() < 0.1 or clock.now() > 0.5,
        bool,
        0.2,
        lambda: None,
    )
    assert reason is None and clock.now() >= 0.7


@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
def test_ui_abort_still_restores_leds(exception: type[BaseException]) -> None:
    hardware = Mock(spec=Hardware)
    hardware.enable = Mock()
    terminal = Mock(spec=m.Terminal)
    terminal.key.side_effect = exception("disconnected")
    with pytest.raises(exception):
        m.ui(hardware, terminal, ["PWR", "WIFI"])
    assert hardware.dark.call_count == 1
    hardware.lights.assert_called_with(0)
    hardware.enable.on.assert_called_once()


@pytest.mark.parametrize("initial", [True, False])
def test_power_detects_both_directions_independently(
    initial: bool, clock: Clock
) -> None:
    hardware = Mock(spec=Hardware)
    terminal = Mock(spec=m.Terminal)
    terminal.rejected.return_value = False
    terminal.key.return_value = ""

    def voltages() -> tuple[float, float]:
        external = initial if clock.now() < 2 or clock.now() >= 4 else not initial
        return (12.0 if external else 0.0, 8.4)

    hardware.voltages.side_effect = voltages
    result = m.power(hardware, terminal, Config())
    assert result.ok and clock.now() >= 5
    hardware.switches.assert_not_called()
    hardware.lights.assert_not_called()


@pytest.mark.parametrize("low_battery", [True, False])
def test_power_low_battery_or_missing_transition_fails(
    low_battery: bool, clock: Clock, capsys: pytest.CaptureFixture[str]
) -> None:
    hardware = Mock(spec=Hardware)
    hardware.voltages.return_value = (12.0, 0.0 if low_battery else 8.4)
    terminal = Mock(spec=m.Terminal)
    terminal.rejected.return_value = False
    terminal.key.return_value = ""
    result = m.power(hardware, terminal, Config())
    assert not result.ok
    text = capsys.readouterr().out
    if low_battery:
        assert "Disconnect" not in text and "Battery" in result.detail
    else:
        assert "timeout" in result.detail and "[2]" not in text


def test_terminal_keyboard_and_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = m.Terminal.__new__(m.Terminal)
    terminal.fd, terminal.previous = 8, None
    original: list[Any] = [1, 2, 3]
    monkeypatch.setattr(m.termios, "tcgetattr", Mock(return_value=original))
    restore = Mock()
    monkeypatch.setattr(m.termios, "tcsetattr", restore)
    monkeypatch.setattr(m.tty, "setcbreak", Mock())
    monkeypatch.setattr(m.select, "select", Mock(return_value=([8], [], [])))
    read = Mock(side_effect=[b"q", b"X", b"x", b"Y", b"N", b"", b"\x04"])
    monkeypatch.setattr(m.os, "read", read)
    terminal.open()
    assert not terminal.rejected()
    assert terminal.rejected() and terminal.rejected()
    assert terminal.key() == "y"
    assert terminal.key() == "n"
    for _ in range(2):
        with pytest.raises(EOFError):
            terminal.rejected()
    terminal.close()
    restore.assert_called_once_with(8, m.termios.TCSANOW, original)


@pytest.mark.parametrize("key", ["y", "n"])
def test_confirmation_keys_do_not_replace_physical_switches(
    key: str, clock: Clock
) -> None:
    terminal = Mock(spec=m.Terminal)
    terminal.key.return_value = key
    reason = m.stage(
        terminal,
        "PWR",
        "Switch PWR OFF",
        lambda: True,
        lambda value: not value,
        0.2,
        lambda: None,
    )
    assert reason == "PWR: timeout"
