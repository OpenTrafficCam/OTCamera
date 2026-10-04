"""System commands, network data paths and the independent modem UART."""

import os
import re
import select
import termios
from pathlib import Path
from time import monotonic

from OTCamera.diagnose.report import Check, output

MIN_ROOT_FREE_BYTES = 1_000_000_000
MIN_BOOT_FREE_BYTES = 100_000_000
MIN_ROOT_CARD_RATIO = 0.90
WATCHDOG_PATH = Path("/sys/class/watchdog/watchdog0")


def watchdog() -> Check:
    """Read the Pi hardware watchdog's runtime state without opening its device."""
    try:
        driver = (WATCHDOG_PATH / "device/driver").resolve(strict=True).name
        identity = (WATCHDOG_PATH / "identity").read_text().strip()
        state = (WATCHDOG_PATH / "state").read_text().strip()
        timeout = int((WATCHDOG_PATH / "timeout").read_text())
        return Check(
            "system.watchdog",
            driver == "bcm2835-wdt" and state == "active" and timeout > 0,
            f"{identity}; {state}; timeout {timeout}s; driver {driver}",
            {
                "driver": driver,
                "identity": identity,
                "state": state,
                "timeout_s": timeout,
            },
        )
    except (OSError, ValueError) as exc:
        return Check("system.watchdog", False, str(exc))


def throttled() -> Check:
    """Check current and historical firmware throttling bits."""
    try:
        value = int(output(["vcgencmd", "get_throttled"]).split("=")[1], 16)
        return Check(
            "power.throttled",
            value == 0,
            f"throttled={value:#x}"
            + ("; undervoltage/throttling occurred" if value else "; no throttling"),
            {
                "throttled": value,
                "undervoltage_now": bool(value & 1),
                "undervoltage_occurred": bool(value & (1 << 16)),
            },
        )
    except Exception as exc:
        return Check("power.throttled", False, str(exc))


def filesystem(path: str) -> tuple[int, int]:
    """Read filesystem size and available bytes."""
    size, free = (
        output(["df", "-B1", "--output=size,avail", path]).splitlines()[-1].split()
    )
    return int(size), int(free)


def expanded() -> Check:
    """Check that the root filesystem occupies most of the card."""
    try:
        card = int(output(["lsblk", "-bdno", "SIZE", "/dev/mmcblk0"]))
        root, _ = filesystem("/")
        ok = card > 0 and root >= card * MIN_ROOT_CARD_RATIO
        return Check(
            "storage.expanded",
            ok,
            "Root filesystem expanded"
            if ok
            else f"Root {root} bytes versus card {card} bytes; expand the filesystem",
            {"root_bytes": root, "card_bytes": card},
        )
    except Exception as exc:
        return Check("storage.expanded", False, str(exc))


def free() -> Check:
    """Check coarse free-space margins on root and boot filesystems."""
    try:
        _, root = filesystem("/")
        _, boot = filesystem("/boot/firmware")
        ok = root >= MIN_ROOT_FREE_BYTES and boot >= MIN_BOOT_FREE_BYTES
        return Check(
            "storage.free",
            ok,
            "Root and boot have free space"
            if ok
            else f"Free bytes: root {root} (need {MIN_ROOT_FREE_BYTES}), boot {boot} (need {MIN_BOOT_FREE_BYTES})",
            {"root_free_bytes": root, "boot_free_bytes": boot},
        )
    except Exception as exc:
        return Check("storage.free", False, str(exc))


def nginx() -> Check:
    """Check the status website service."""
    try:
        values = dict(
            line.split("=", 1)
            for line in output(
                [
                    "systemctl",
                    "show",
                    "nginx.service",
                    "-p",
                    "ActiveState",
                    "-p",
                    "SubState",
                ]
            ).splitlines()
        )
        return Check(
            "service.nginx",
            values.get("ActiveState") == "active",
            f"{values.get('ActiveState')} ({values.get('SubState')})",
        )
    except Exception as exc:
        return Check("service.nginx", False, str(exc))


def otcamera_loaded() -> Check:
    """Check that the OTCamera unit is loaded regardless of autostart state."""
    try:
        state = output(
            ["systemctl", "show", "otcamera.service", "-p", "LoadState", "--value"]
        )
        return Check("service.otcamera", state == "loaded", f"LoadState={state}")
    except Exception as exc:
        return Check("service.otcamera", False, str(exc))


def connect() -> Check:
    """Check the user's Raspberry Pi Connect authentication and event connection."""
    try:
        value = output(["rpi-connect", "status"])
        values = dict(line.split(":", 1) for line in value.splitlines() if ":" in line)
        ok = all(
            values.get(key, "").strip() == "yes"
            for key in ("Signed in", "Subscribed to events")
        )
        ok = ok and values.get("Remote shell", "").strip().startswith("allowed")
        return Check("connect.remote", ok, value.replace("\n", "; "))
    except Exception as exc:
        return Check("connect.remote", False, str(exc))


def network(lte: bool = False) -> Check:
    """Judge the interface address and route, retaining modem state as context."""
    check_id, interface = ("net.lte", "wwan0") if lte else ("net.wlan", "wlan0")
    try:
        addresses = output(["ip", "-4", "-br", "addr", "show", interface])
        has_address = bool(re.search(r"\b\d+\.\d+\.\d+\.\d+/\d+", addresses))
        routes = output(["ip", "-4", "route", "show", "default"])
        has_route = any(
            re.search(rf"\bdev {interface}(?:\s|$)", line)
            for line in routes.splitlines()
        )
        ok = has_address and has_route
        measured = {}
        detail = f"{interface}: address {'present' if has_address else 'missing'}, default route {'present' if has_route else 'missing'}"
        if not lte:
            connection = output(
                ["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", interface]
            )
            ok = ok and connection not in ("", "--")
            detail += f"; connection {connection}"
        # Supplemental metadata cannot invalidate a healthy data path.
        try:
            if lte:
                values = dict(
                    (key.strip(), value.strip())
                    for line in output(["mmcli", "-m", "0", "-K"]).splitlines()
                    if ":" in line
                    for key, value in [line.split(":", 1)]
                )
                state = values.get("modem.generic.state", "unknown")
                registration = values.get("modem.3gpp.registration-state", "unknown")
                registered = state in (
                    "registered",
                    "connecting",
                    "connected",
                    "disconnecting",
                ) or registration in ("home", "roaming")
                detail += f"; modem {state}, {registration}; " + (
                    "registered" if registered else "no network registration"
                )
                measured = {
                    "signal_pct": int(values["modem.generic.signal-quality.value"]),
                    "access_tech": values.get(
                        "modem.generic.access-technologies.value[1]", ""
                    ),
                    "operator_code": values.get("modem.3gpp.operator-code", ""),
                }
            else:
                wifi = output(
                    [
                        "nmcli",
                        "-t",
                        "-f",
                        "IN-USE,SSID,SIGNAL",
                        "device",
                        "wifi",
                        "list",
                        "ifname",
                        interface,
                        "--rescan",
                        "no",
                    ]
                )
                for line in wifi.splitlines():
                    if line.startswith("*:"):
                        ssid, signal = line[2:].rsplit(":", 1)
                        detail += f"; SSID {ssid}"
                        measured = {"signal_pct": int(signal)}
        except Exception as exc:
            detail += f"; metadata unavailable: {exc}"
        return Check(check_id, ok, detail, measured)
    except Exception as exc:
        return Check(check_id, False, str(exc))


def at(command: str, timeout: float = 3) -> str:
    """Exchange one AT command on serial0 at 115200 8N1 without flow control."""
    fd = os.open("/dev/serial0", os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        settings = termios.tcgetattr(fd)
        settings[0] = settings[1] = settings[3] = 0
        settings[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        settings[4] = settings[5] = termios.B115200
        settings[6][termios.VMIN] = 0
        settings[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, settings)
        termios.tcflush(fd, termios.TCIOFLUSH)
        os.write(fd, (command + "\r").encode("ascii"))
        deadline, response = monotonic() + timeout, b""
        while (remaining := deadline - monotonic()) > 0:
            if select.select([fd], [], [], remaining)[0]:
                response += os.read(fd, 4096)
                lines = response.decode("ascii", errors="replace").splitlines()
                if any(
                    line.strip() == "ERROR"
                    or line.startswith(("+CME ERROR", "+CMS ERROR"))
                    for line in lines
                ):
                    raise RuntimeError(
                        f"{command}: {response.decode('ascii', errors='replace').strip()}"
                    )
                if any(line.strip() == "OK" for line in lines):
                    return "\n".join(
                        line.strip()
                        for line in lines
                        if line.strip() not in ("", command, "OK")
                    )
        raise TimeoutError(
            f"UART /dev/serial0 did not complete {command}: {response!r}"
        )
    finally:
        os.close(fd)


def modem_at() -> Check:
    """Verify the UART independently of the USB modem data path."""
    try:
        response = at("ATI")
        return Check(
            "modem.at",
            bool(response),
            "; ".join(response.splitlines()) or "Empty modem identification",
        )
    except Exception as exc:
        return Check("modem.at", False, str(exc))


def gnss_engine() -> Check:
    """Check the GNSS engine without changing its state."""
    try:
        response = at("AT+QGPS?")
        ok = bool(re.search(r"\+QGPS:\s*1\b", response))
        return Check(
            "gnss.engine",
            ok,
            "GNSS engine running"
            if ok
            else f"GNSS engine not enabled: {response}; check autogps provisioning",
        )
    except Exception as exc:
        return Check("gnss.engine", False, f"Cannot query GNSS engine over UART: {exc}")


def gnss_nmea() -> Check:
    """Accept a GGA sentence without requiring an indoor satellite fix."""
    try:
        gga = at('AT+QGPSGNMEA="GGA"')
        sentence = re.search(r"\$[A-Z]{2}GGA,[^\r\n]*", gga)
        ok = sentence is not None
        detail = "No GGA sentence returned"
        if sentence:
            fields = sentence[0].split(",")
            quality = fields[6].split("*")[0] if len(fields) > 6 else ""
            fix = (
                "no fix"
                if quality == "0"
                else (
                    f"fix available (quality {quality})"
                    if quality.isdigit()
                    else "fix status unknown"
                )
            )
            detail = f"GGA received; {fix}"
        try:
            gsv = at('AT+QGPSGNMEA="GSV"')
            satellites = re.search(r"\$[A-Z]{2}GSV,\d+,\d+,(\d+)", gsv)
            detail += (
                f"; satellites in view: {satellites[1] if satellites else 'unknown'}"
            )
        except Exception as exc:
            detail += f"; GSV unavailable: {exc}"
        try:
            status = output(["mmcli", "-m", "0", "--location-status"])
            capabilities: list[str] = []
            for line in status.splitlines():
                if "capabilities:" in line:
                    capabilities.append(line.split("capabilities:", 1)[1].strip())
                elif capabilities:
                    continuation = line.partition("|")[2].strip()
                    if not continuation or ":" in continuation:
                        break
                    capabilities.append(continuation)
            detail += "; location capabilities: " + (
                " ".join(capabilities) or "unknown"
            )
        except Exception as exc:
            detail += f"; location capabilities unavailable: {exc}"
        return Check("gnss.nmea", ok, detail)
    except Exception as exc:
        return Check("gnss.nmea", False, f"Cannot read NMEA over UART: {exc}")
