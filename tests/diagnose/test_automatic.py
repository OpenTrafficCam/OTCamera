"""Independent measurements and declared hardware selection."""

from unittest.mock import Mock

import pytest

from OTCamera.bsl.board_provider import load_board_definition
from OTCamera.config import Config
from OTCamera.diagnose import automatic as a
from OTCamera.diagnose.hardware import Hardware, adc_check


@pytest.mark.parametrize("lte", [False, True])
def test_measurement_failures_do_not_stop_independent_checks(
    lte: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    hardware = Hardware(load_board_definition("v20d"))
    for module, names in (
        (a.i2c, ["chip", "scan", "rtc_hctosys", "rtc_state"]),
        (
            a.probes,
            [
                "throttled",
                "watchdog",
                "expanded",
                "free",
                "nginx",
                "otcamera_loaded",
                "connect",
                "network",
                "modem_at",
                "gnss_engine",
                "gnss_nmea",
            ],
        ),
        (a.camera, ["present"]),
    ):
        for name in names:
            monkeypatch.setattr(
                module, name, Mock(side_effect=OSError("device unavailable"))
            )
    monkeypatch.setattr(
        hardware, "open_adc", Mock(side_effect=OSError("ADC unavailable"))
    )
    capture = Mock(side_effect=AssertionError("auto must not capture"))
    gpio = Mock(side_effect=AssertionError("auto must not acquire GPIO"))
    monkeypatch.setattr(a.camera, "capture", capture)
    monkeypatch.setattr(hardware, "open_gpio", gpio)
    config = Config.model_validate({"hardware": {"pcb_version": "v20d"}})
    checks = list(a.inspect(config, "v20d", lte, hardware))
    ids = {c.id for c in checks}
    assert len(checks) == (23 if lte else 19) == len(ids)
    assert {"camera.present", "i2c.tla2024", "storage.free", "system.watchdog", "service.otcamera"} <= ids
    assert ("gnss.nmea" in ids) == lte
    assert checks[0].ok and all(not c.ok for c in checks[2:])
    capture.assert_not_called()
    gpio.assert_not_called()


@pytest.mark.parametrize(
    "configured,declared,ok",
    [("v20d", "v20d", True), ("v2", "v16b", True), ("v2", "v20d", False)],
)
def test_board_alias_and_mismatch(configured: str, declared: str, ok: bool) -> None:
    config = Config.model_validate({"hardware": {"pcb_version": configured}})
    assert a.board_revision(config, declared).ok == ok


def test_adc_scaling_and_field_names() -> None:
    board = load_board_definition("v20d")
    hardware = Hardware(board)
    adc = Mock()
    adc.get_voltage.side_effect = [1.0, 2.5]
    hardware.adc = adc
    result = adc_check(hardware, 6.4)
    assert result.ok
    assert result.measured == {
        "usb_voltage_v": board.adc_divider_ratio_usb,
        "battery_voltage_v": 2.5 * board.adc_divider_ratio_battery,
    }


@pytest.mark.parametrize(
    "battery,threshold,ok",
    [(6.39, 6.4, False), (6.4, 6.4, True), (7.0, 6.4, True), (7.0, 7.2, False)],
)
def test_automatic_battery_threshold(
    battery: float, threshold: float, ok: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    hardware = Hardware(load_board_definition("v20d"))
    monkeypatch.setattr(hardware, "open_adc", Mock())
    monkeypatch.setattr(hardware, "voltages", Mock(return_value=(5.0, battery)))
    config = Config.model_validate({"adc": {"threshold_low_battery": threshold}})
    checks = a.inspect(config, "v20d", False, hardware)
    # Skip unrelated I2C probes while retaining the real ADC check and config wiring.
    monkeypatch.setattr(a.i2c, "chip", Mock())
    result = next(check for check in checks if check is not None and check.id == "i2c.tla2024")
    assert result.ok is ok
    assert result.measured["battery_voltage_v"] == battery
    assert result.measured["usb_voltage_v"] == 5.0
    if not ok:
        assert result.detail == f"Battery {battery:.2f} V below {threshold:.2f} V"


@pytest.mark.parametrize("state", ["loaded", "not-found", "error", "bad-setting", "masked"])
def test_otcamera_load_state_only(state: str, monkeypatch: pytest.MonkeyPatch) -> None:
    command = Mock(return_value=state)
    monkeypatch.setattr(a.probes, "output", command)
    check = a.probes.otcamera_loaded()
    assert check.id == "service.otcamera"
    assert check.ok == (state == "loaded")
    command.assert_called_once_with(["systemctl", "show", "otcamera.service", "-p", "LoadState", "--value"])


def test_otcamera_load_state_query_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a.probes, "output", Mock(side_effect=OSError("unavailable")))
    assert not a.probes.otcamera_loaded().ok
