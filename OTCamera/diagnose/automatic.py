"""Independent automatic checks assembled from the approved measurements."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from OTCamera.config import Config
from OTCamera.diagnose import camera, i2c, probes
from OTCamera.diagnose.catalog import EXPECTED_POPULATION
from OTCamera.diagnose.hardware import Hardware, adc_check
from OTCamera.diagnose.report import Check


def board_revision(config: Config, revision: str) -> Check:
    """Compare configured and declared board names, retaining the legacy alias."""
    configured = config.hardware.pcb_version
    aliases = {"v2": "v16b"}
    return Check(
        "config.board_revision",
        aliases.get(configured, configured) == aliases.get(revision, revision),
        f"Configured {configured}; provisioned {revision}",
    )


def _check(
    check_id: str, measure: Callable[..., Check], *args: Any, **kwargs: Any
) -> Check:
    try:
        return measure(*args, **kwargs)
    except Exception as exc:
        return Check(check_id, False, str(exc))


def inspect(
    config: Config, revision: str, lte: bool, hardware: Hardware
) -> Iterator[Check]:
    """Yield every independent check so guided can checkpoint each result."""
    board = hardware.board
    population = EXPECTED_POPULATION[revision]
    yield board_revision(config, revision)
    path = Path(f"/dev/i2c-{board.adc_i2c_bus}")
    try:
        yield Check("board.i2c_bus", path.exists(), str(path))
    except OSError as exc:
        yield Check("board.i2c_bus", False, str(exc))
    for name, address in population:
        yield _check(f"i2c.{name}", i2c.chip, board.adc_i2c_bus, name, address)
    yield _check("i2c.tla2024", adc_check, hardware, config.adc.threshold_low_battery)
    yield _check("i2c.scan", i2c.scan, board, population)
    yield _check("rtc.hctosys", i2c.rtc_hctosys)
    yield _check("rtc.state", i2c.rtc_state)
    yield _check("power.throttled", probes.throttled)
    yield _check("system.watchdog", probes.watchdog)
    yield _check("storage.expanded", probes.expanded)
    yield _check("storage.free", probes.free)
    yield _check("service.nginx", probes.nginx)
    yield _check("service.otcamera", probes.otcamera_loaded)
    yield _check("connect.remote", probes.connect)
    yield _check("net.wlan", probes.network)
    yield _check("camera.present", camera.present)
    if lte:
        yield _check("net.lte", probes.network, lte=True)
        yield _check("modem.at", probes.modem_at)
        yield _check("gnss.engine", probes.gnss_engine)
        yield _check("gnss.nmea", probes.gnss_nmea)
