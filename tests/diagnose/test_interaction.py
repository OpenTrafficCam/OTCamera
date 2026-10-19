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


@pytest.mark.parametrize("failure", [None, *range(7)])
@pytest.mark.parametrize("mode", ["reject", "timeout"])
def test_ui_stops_at_first_failure_and_restores_leds(
    failure: int | None, mode: str, clock: Clock, capsys: pytest.CaptureFixture[str]
) -> None:
    hardware = Mock(spec=Hardware)
    hardware.enable = Mock()
    hardware.leds = [Mock() for _ in range(4)]
    terminal = Mock(spec=m.Terminal)
    phase, entered, boundary = -1, 0.0, 0
    states: tuple[bool, ...] = (False,) * 4

    def flush() -> None:
        nonlocal phase, entered, boundary
        if boundary % 2 == 0:
            phase += 1
            entered = clock.now()
        boundary += 1

    def switches() -> tuple[bool, ...]:
        nonlocal states
        if phase == failure or clock.now() - entered < 0.3:
            return states
        if phase == 0:
            states = (False,) * 4
        elif phase <= 4:
            states = tuple(i < phase for i in range(4))
        elif phase == 5:
            states = (True, True, True, False)
        else:
            states = (False,) * 4
        return states

    terminal.flush.side_effect = flush
    terminal.rejected.side_effect = lambda: mode == "reject" and phase == failure
    hardware.switches.side_effect = switches
    # The initial stage needs a wrong state to exercise its timeout.
    if failure == 0 and mode == "timeout":
        states = (True,) * 4
    result = m.ui(hardware, terminal)
    assert result.ok == (failure is None)
    assert phase == (6 if failure is None else failure)
    assert hardware.dark.call_count == 1
    hardware.lights.assert_called_with(0)
    hardware.enable.on.assert_called_once()
    text = capsys.readouterr().out
    assert "Restore" not in text and "wait for the request" not in text
    assert "[##############################] 30 s" in text
    if failure == 0 and mode == "timeout":
        assert "[##########--------------------] 10 s" in text
    if failure is not None:
        assert ("rejected" if mode == "reject" else "timeout") in result.detail
        assert clock.now() < m.STAGE_SECONDS + 10
    else:
        assert "Switch LIGHT_Button ON" in text
        assert "Are ALL LEDs OFF?" in text
        assert "Switch LIGHT_Button OFF only." in text
        assert "Switch all buttons OFF." in text
        assert states == (False,) * 4
        hardware.enable.off.assert_called_once()
        assert all(led.on.call_count == 1 for led in hardware.leds)


def test_unexpected_switch_stops_stage(clock: Clock) -> None:
    terminal = Mock(spec=m.Terminal)
    terminal.rejected.return_value = False
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
    terminal.rejected.side_effect = exception("disconnected")
    with pytest.raises(exception):
        m.ui(hardware, terminal)
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
    result = m.power(hardware, terminal, Config())
    assert not result.ok
    text = capsys.readouterr().out
    if low_battery:
        assert "Disconnect" not in text and "Battery" in result.detail
    else:
        assert "timeout" in result.detail and "[9]" not in text


def test_terminal_keyboard_and_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = m.Terminal.__new__(m.Terminal)
    terminal.fd, terminal.previous = 8, None
    original: list[Any] = [1, 2, 3]
    monkeypatch.setattr(m.termios, "tcgetattr", Mock(return_value=original))
    restore = Mock()
    monkeypatch.setattr(m.termios, "tcsetattr", restore)
    monkeypatch.setattr(m.tty, "setcbreak", Mock())
    monkeypatch.setattr(m.select, "select", Mock(return_value=([8], [], [])))
    read = Mock(side_effect=[b"q", b"X", b"x", b"", b"\x04"])
    monkeypatch.setattr(m.os, "read", read)
    terminal.open()
    assert not terminal.rejected()
    assert terminal.rejected() and terminal.rejected()
    for _ in range(2):
        with pytest.raises(EOFError):
            terminal.rejected()
    terminal.close()
    restore.assert_called_once_with(8, m.termios.TCSANOW, original)
