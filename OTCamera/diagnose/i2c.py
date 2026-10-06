"""I2C_RDWR identification, population scan and read-only RTC diagnostics."""

from datetime import datetime, timezone
from pathlib import Path
from time import sleep

from OTCamera.bsl.boards.board import Board
from OTCamera.diagnose.catalog import CHIPS
from OTCamera.diagnose.report import Check

RTC = Path("/sys/class/rtc/rtc0")


def bus_present(path: Path) -> Check:
    """Check whether the board's I2C device exists."""
    return Check("board.i2c_bus", path.exists(), str(path))


def read(
    bus: int, address: int, register: int, count: int, delay: float = 0
) -> list[int]:
    """Read a register or conversion without claiming a kernel-owned slave."""
    from smbus2 import SMBus, i2c_msg

    with SMBus(bus) as device:
        request = i2c_msg.write(address, [register])
        response = i2c_msg.read(address, count)
        if delay:
            device.i2c_rdwr(request)
            sleep(delay)
            device.i2c_rdwr(response)
        else:
            device.i2c_rdwr(request, response)
        return list(response)


def crc8(data: list[int]) -> int:
    """Calculate the SHT4x CRC-8."""
    crc = 0xFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ (0x31 if crc & 0x80 else 0)) & 0xFF
    return crc


def chip(bus: int, name: str, address: int) -> Check:
    """Distinguish missing acknowledgements, wrong identities and valid replies."""
    try:
        from smbus2 import SMBus, i2c_msg

        # SHT40 NACKs a bare read; a zero-byte write also detects this device.
        with SMBus(bus) as device:
            device.i2c_rdwr(i2c_msg.write(address, []))
        register, mask, shift, expected = CHIPS[name]
        if name == "sht40":
            values = read(bus, address, register, 6, 0.01)
            ok = crc8(values[:2]) == values[2] and crc8(values[3:5]) == values[5]
            detail = (
                "SHT4x-compatible reply, both CRCs valid"
                if ok
                else f"Invalid SHT4x CRC: {values}"
            )
        else:
            value = (read(bus, address, register, 1)[0] & mask) >> shift
            ok = value in expected
            detail = (
                f"identity {value:#x} matches"
                if ok
                else f"identity read {value:#x}, expected {expected}"
            )
        return Check(f"i2c.{name}", ok, f"{address:#04x}: {detail}")
    except Exception as exc:
        return Check(
            f"i2c.{name}",
            False,
            f"{address:#04x}: no valid reply; missing device or bus wiring: {exc}",
        )


def rtc_address() -> tuple[int, int]:
    """Read the actual kernel-bound RTC bus and address."""
    bus, address = (RTC / "name").read_text().split()[-1].split("-")
    return int(bus), int(address, 16)


def scan(board: Board, population: tuple[tuple[str, int], ...]) -> Check:
    """Fail for missing expected addresses, while reporting additional devices."""
    try:
        from smbus2 import SMBus, i2c_msg

        expected = {address for _, address in population} | {board.adc_i2c_address}
        if (RTC / "name").exists():
            rtc_bus, address = rtc_address()
            if rtc_bus == board.adc_i2c_bus:
                expected.add(address)
        found = set()
        with SMBus(board.adc_i2c_bus) as device:
            for address in range(0x08, 0x78):
                try:
                    device.i2c_rdwr(i2c_msg.write(address, []))
                    found.add(address)
                except OSError:
                    pass
        missing, unexpected = expected - found, found - expected
        measured = {
            key: [f"{value:#04x}" for value in sorted(values)]
            for key, values in (
                ("found", found),
                ("missing", missing),
                ("unexpected", unexpected),
            )
        }
        detail = (
            f"Missing addresses {measured['missing']}"
            if missing
            else "All expected addresses acknowledge"
        )
        if unexpected:
            detail += f"; additional devices {measured['unexpected']}"
        return Check("i2c.scan", not missing, detail, measured)
    except Exception as exc:
        return Check("i2c.scan", False, str(exc))


def rtc_hctosys() -> Check:
    """Check whether the kernel could initialize system time from the RTC."""
    try:
        if not RTC.exists():
            return Check(
                "rtc.hctosys", False, "rtc0 is missing; check the i2c-rtc overlay"
            )
        ok = (RTC / "hctosys").read_text().strip() == "1"
        detail = "Kernel initialized time from RTC"
        if not ok:
            detail = (
                "hctosys=0; kernel did not initialize system time from RTC; "
                "inspect kernel logs with journalctl -b -k"
            )
        return Check("rtc.hctosys", ok, detail)
    except Exception as exc:
        return Check("rtc.hctosys", False, str(exc))


def rtc_state() -> Check:
    """Judge oscillator and battery bits; report offset from system time."""
    try:
        bus, address = rtc_address()
        raw = read(bus, address, 0, 7)
        bits = {
            "st": bool(raw[0] & 0x80),
            "oscrun": bool(raw[3] & 0x20),
            "vbaten": bool(raw[3] & 0x08),
        }
        values = [
            (value & mask)
            for value, mask in zip(raw, (0x7F, 0x7F, 0x3F, 0x07, 0x3F, 0x1F, 0xFF))
        ]
        values = [(value >> 4) * 10 + (value & 15) for value in values]
        second, minute, hour, _, day, month, year = values
        if raw[2] & 0x40:
            hour = ((raw[2] & 0x10) >> 4) * 10 + (raw[2] & 15)
            hour = hour % 12 + (12 if raw[2] & 0x20 else 0)
        stamp = datetime(
            2000 + year, month, day, hour, minute, second, tzinfo=timezone.utc
        )
        offset = (stamp - datetime.now(timezone.utc)).total_seconds()
        ok = all(bits.values())
        return Check(
            "rtc.state",
            ok,
            f"RTC offset from system time {offset:.1f} s; "
            + (
                "oscillator and battery enabled"
                if ok
                else f"invalid status bits {bits}"
            ),
            {"drift_s": offset, **bits},
        )
    except Exception as exc:
        return Check("rtc.state", False, str(exc))
