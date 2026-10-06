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


def check_plan(
    config: Config, revision: str, lte: bool, hardware: Hardware
) -> list[tuple[str, Callable[..., Check], tuple[Any, ...]]]:
    """Prepare automatic checks without executing them."""
    board = hardware.board
    population = EXPECTED_POPULATION[revision]
    path = Path(f"/dev/i2c-{board.adc_i2c_bus}")
    checks: list[tuple[str, Callable[..., Check], tuple[Any, ...]]] = [
        ("config.board_revision", board_revision, (config, revision)),
        ("board.i2c_bus", i2c.bus_present, (path,)),
    ]
    for name, address in population:
        checks.append((f"i2c.{name}", i2c.chip, (board.adc_i2c_bus, name, address)))
    checks.extend(
        [
            (
                "i2c.tla2024",
                adc_check,
                (hardware, config.adc.threshold_low_battery),
            ),
            ("i2c.scan", i2c.scan, (board, population)),
            ("rtc.hctosys", i2c.rtc_hctosys, ()),
            ("rtc.state", i2c.rtc_state, ()),
            ("power.throttled", probes.throttled, ()),
            ("system.watchdog", probes.watchdog, ()),
            ("storage.expanded", probes.expanded, ()),
            ("storage.free", probes.free, ()),
            ("service.nginx", probes.nginx, ()),
            ("service.otcamera", probes.otcamera_loaded, ()),
            ("connect.remote", probes.connect, ()),
            ("net.wlan", probes.network, ()),
            ("camera.present", camera.present, ()),
        ]
    )
    if lte:
        checks.extend(
            [
                ("net.lte", probes.network, (True,)),
                ("modem.at", probes.modem_at, ()),
                ("gnss.engine", probes.gnss_engine, ()),
                ("gnss.nmea", probes.gnss_nmea, ()),
            ]
        )
    return checks


def inspect(
    config: Config, revision: str, lte: bool, hardware: Hardware
) -> Iterator[Check]:
    """Yield every independent check so guided can checkpoint each result."""
    for check_id, function, args in check_plan(config, revision, lte, hardware):
        yield _check(check_id, function, *args)
