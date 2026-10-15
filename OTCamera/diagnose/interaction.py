"""Bounded physical stages and immediate keyboard rejection on a terminal."""

import math
import os
import select
import sys
import termios
import tty
from collections.abc import Callable
from time import monotonic, sleep
from typing import Any

from OTCamera.config import Config
from OTCamera.diagnose.hardware import SWITCHES, Hardware
from OTCamera.diagnose.report import Check

STAGE_SECONDS = 30.0
SWITCH_STABLE_SECONDS = 0.2
SUPPLY_STABLE_SECONDS = 1.0
LED_SLOT_SECONDS = 0.15
POLL_SECONDS = 0.02
UI_CHECK_COUNT = 1
POWER_CHECK_COUNT = 1


class Terminal:
    """Restore terminal state while allowing immediate keys and signal interrupts."""

    def __init__(self) -> None:
        self.fd = sys.stdin.fileno()
        self.previous: list[Any] | None = None

    def open(self) -> None:
        """Enter cbreak mode, retaining Ctrl-C signal delivery."""
        self.previous = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)

    def close(self) -> None:
        """Restore the exact settings that preceded the inspection."""
        if self.previous is not None:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.previous)

    def flush(self) -> None:
        """Discard pending input at every stage boundary."""
        termios.tcflush(self.fd, termios.TCIFLUSH)

    def key(self) -> str:
        """Read one available key; EOF/disconnection aborts the run."""
        if not select.select([self.fd], [], [], 0)[0]:
            return ""
        key = os.read(self.fd, 1)
        if not key or key == b"\x04":
            raise EOFError("Terminal disconnected or EOF")
        return key.decode("ascii", errors="ignore").lower()

    def rejected(self) -> bool:
        """Allow immediate rejection during the initial supply measurement."""
        return self.key() == "x"


def color(text: str, code: str) -> str:
    """Style terminal text while respecting plain-output preferences."""
    if (
        not sys.stdout.isatty()
        or "NO_COLOR" in os.environ
        or os.environ.get("TERM") == "dumb"
    ):
        return text
    return f"\033[{code}m{text}\033[0m"


def section(title: str) -> None:
    """Separate inspection areas in the terminal output."""
    sys.stdout.write(f"\n{'=' * 50}\n{title}\n{'=' * 50}\n")
    sys.stdout.flush()


def stage(
    terminal: Terminal,
    name: str,
    instruction: str,
    sample: Callable[[], Any],
    target: Callable[[Any], bool],
    stable_seconds: float,
    tick: Callable[[], None],
    unexpected: Callable[[Any], bool] | None = None,
    *,
    confirmation: bool = False,
) -> str | None:
    """Wait for a stable result, stopping immediately on rejection or failure."""
    terminal.flush()
    heading, separator, details = instruction.partition("\n")
    sys.stdout.write(f"\n{color(heading, '1;36')}\n{'-' * 50}\n")
    if separator:
        sys.stdout.write(details.lstrip("\n") + "\n\n")
    deadline = monotonic() + STAGE_SECONDS
    since: float | None = None
    unexpected_since: float | None = None
    displayed = -1
    try:
        while (remaining := deadline - monotonic()) > 0:
            tick()
            seconds = math.ceil(remaining)
            if seconds != displayed:
                width = 30
                filled = math.ceil(width * seconds / STAGE_SECONDS)
                bar = "#" * filled + "-" * (width - filled)
                sys.stdout.write(f"\r[{bar}] {seconds:2d} s")
                sys.stdout.flush()
                displayed = seconds
            key = terminal.key()
            if key == "x" or (confirmation and key == "n"):
                return f"{name}: rejected by operator"
            if confirmation and key == "y":
                return None
            value = sample()
            now = monotonic()
            if unexpected is not None and unexpected(value):
                if unexpected_since is None:
                    unexpected_since = now
                elif now - unexpected_since >= stable_seconds:
                    return f"{name}: unexpected other switch transition"
            else:
                unexpected_since = None
            if target(value):
                if since is None:
                    since = now
                elif now - since >= stable_seconds:
                    return None
            else:
                since = None
            sleep(POLL_SECONDS)
        return f"{name}: timeout"
    finally:
        sys.stdout.write("\n")
        terminal.flush()


def ui(hardware: Hardware, terminal: Terminal, fitted_switches: list[str]) -> Check:
    """Test fitted switches and confirm LED behavior independently by keyboard."""
    names = [name for name in SWITCHES if name in fitted_switches]

    def running_light() -> None:
        hardware.lights(int(monotonic() / LED_SLOT_SECONDS) % 4)

    def sequence() -> str | None:
        step = 1
        if names:
            reason = stage(
                terminal,
                "Baseline",
                f"[{step}] Switch all buttons ON",
                hardware.switches,
                lambda s: all(s),
                SWITCH_STABLE_SECONDS,
                lambda: None,
            )
            if reason:
                return reason
            step += 1
        for index, name in enumerate(names):
            before = tuple(i >= index for i in range(len(names)))
            after = tuple(i > index for i in range(len(names)))
            reason = stage(
                terminal,
                f"{name} OFF",
                f"[{step}] Switch {name}_Button OFF",
                hardware.switches,
                lambda s: s == after,
                SWITCH_STABLE_SECONDS,
                lambda: None,
                lambda s: any(
                    s[i] != before[i] for i in range(len(names)) if i != index
                ),
            )
            if reason:
                return reason
            step += 1
        reason = stage(
            terminal,
            "running light",
            f"[{step}] Are all four LEDs blinking in order?\n"
            "PWR_RPI -> WIFI_EN -> RECORD -> INTRUSION\n\n"
            "YES: Press Y.\n NO: Press N or X.",
            lambda: None,
            lambda _: False,
            0,
            running_light,
            confirmation=True,
        )
        if reason:
            return reason
        hardware.lights()
        hardware.enable.off()
        for led in hardware.leds:
            led.on()
        return stage(
            terminal,
            "LED enable",
            f"[{step + 1}] Are ALL LEDs OFF?\n\nYES: Press Y.\n NO: Press N or X.",
            lambda: None,
            lambda _: False,
            0,
            lambda: None,
            confirmation=True,
        )

    reason = None
    try:
        hardware.open_gpio(fitted_switches)
        hardware.dark()
        reason = sequence()
    except EOFError:
        raise
    except Exception as exc:
        reason = f"UI hardware: {exc}"
    finally:
        if hardware.enable is not None:
            try:
                hardware.lights(0)
                hardware.enable.on()
            except Exception as exc:
                reason = f"{reason + '; ' if reason else ''}Prepare supply LEDs: {exc}"
    return Check(
        "ui",
        reason is None,
        reason or "Fitted switches, running light and LED enable verified",
        {"fitted_switches": names},
    )


def power(hardware: Hardware, terminal: Terminal, config: Config) -> Check:
    """Verify electrical supply transitions independently of UI acceptance."""
    threshold = config.adc.threshold_external_power
    low = config.adc.threshold_low_battery
    try:
        hardware.open_adc()
        # Establish a stable initial state without inviting a supply action.
        deadline = monotonic() + STAGE_SECONDS
        initial, battery = hardware.voltages()
        since = monotonic()
        initial_on = initial >= threshold
        sys.stdout.write(
            "\nMeasuring initial supply state; keep the supply unchanged.\n"
        )
        terminal.flush()
        while monotonic() - since < SUPPLY_STABLE_SECONDS:
            if terminal.rejected():
                return Check(
                    "power.switchover", False, "initial supply: rejected by operator"
                )
            if monotonic() >= deadline:
                return Check("power.switchover", False, "initial supply: unstable")
            external, battery = hardware.voltages()
            on = external >= threshold
            if on != initial_on:
                since, initial_on = monotonic(), on
            sleep(POLL_SECONDS)
        if battery < low:
            return Check(
                "power.switchover",
                False,
                f"Battery {battery:.2f} V below {low:.2f} V; supply switching skipped",
            )

        def sample() -> bool:
            external, _ = hardware.voltages()
            return external >= threshold

        first = stage(
            terminal,
            "Supply transition",
            "[1] Disconnect external supply"
            if initial_on
            else "[1] Connect external supply",
            sample,
            lambda s: s != initial_on,
            SUPPLY_STABLE_SECONDS,
            lambda: None,
        )
        if first:
            return Check(
                "power.switchover",
                False,
                first + "; Supply return: missing verified first transition",
            )
        if not initial_on:
            _, battery = hardware.voltages()
            if battery < low:
                return Check(
                    "power.switchover",
                    False,
                    f"Supply return: battery {battery:.2f} V below {low:.2f} V; disconnection skipped",
                )
        second = stage(
            terminal,
            "Supply return",
            "[2] Reconnect external supply"
            if initial_on
            else "[2] Disconnect external supply to restore initial state",
            sample,
            lambda s: s == initial_on,
            SUPPLY_STABLE_SECONDS,
            lambda: None,
        )
        return Check(
            "power.switchover",
            second is None,
            second or "Both supply transitions verified",
        )
    except EOFError:
        raise
    except Exception as exc:
        return Check("power.switchover", False, str(exc))
