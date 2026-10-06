"""Acceptance criteria for the retained measurement and identity modules."""

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

from OTCamera.config import Config
from OTCamera.diagnose import camera, facts, i2c, probes, provisioning
from OTCamera.diagnose.report import Check, Report, ToolError


@pytest.mark.parametrize("initialized", [False, True])
def test_rtc_hctosys_reports_status_without_running_commands(
    initialized: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(i2c, "RTC", tmp_path)
    (tmp_path / "hctosys").write_text("1\n" if initialized else "0\n")
    command = Mock(side_effect=AssertionError("must not run journalctl"))
    monkeypatch.setattr("subprocess.run", command)
    result = i2c.rtc_hctosys()
    assert result.id == "rtc.hctosys"
    assert result.ok is initialized
    if initialized:
        assert result.detail == "Kernel initialized time from RTC"
    else:
        assert "hctosys=0" in result.detail
        assert "inspect kernel logs with journalctl -b -k" in result.detail
    command.assert_not_called()


@pytest.mark.parametrize(
    "declared",
    [
        "{}",
        "{hardware_revision: v20d}",
        "{hardware_revision: '', has_lte_module: false}",
        "{hardware_revision: v20d, has_lte_module: 'false'}",
    ],
)
def test_provisioning_rejects_incomplete_declaration(
    declared: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "provisioning.yml"
    path.write_text(f"provisioning: {{}}\ndeclared: {declared}\n")
    monkeypatch.setattr(provisioning, "PROVISIONING_PATH", path)
    with pytest.raises(ToolError):
        provisioning.load_provisioning()


def test_provenance_retained_when_identity_sources_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "provisioning.yml"
    path.write_text(
        "provisioning: {timestamp: 2026-09-30T12:00:00Z, extra: retained}\ndeclared: {hardware_revision: v20d, has_lte_module: false, extra: retained}\n"
    )
    monkeypatch.setattr(provisioning, "PROVISIONING_PATH", path)
    manifest = provisioning.load_provisioning()
    monkeypatch.setattr(facts, "output", Mock(side_effect=OSError("missing")))
    monkeypatch.setattr(facts, "at", Mock(side_effect=OSError("missing")))
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=OSError("missing")))
    monkeypatch.setitem(
        sys.modules,
        "picamera2",
        SimpleNamespace(Picamera2=Mock(global_camera_info=Mock(return_value=[]))),
    )
    result = facts.collect(manifest)
    assert list(result["device"]) == [
        "hostname",
        "model",
        "revision",
        "serial",
        "wlan_mac",
    ]
    assert result["device"]["hostname"] and result["device"]["serial"] == ""
    assert result["provisioning"]["declared"] == manifest["declared"]
    assert result["provisioning"]["extra"] == "retained"
    assert list(result["software"]["otcamera"]) == [
        "version",
        "git_commit",
        "git_describe",
    ]
    assert "ssh_host_key" not in str(result)


@pytest.mark.parametrize(
    "name,value,ok",
    [
        ("lis2dw12", 0x44, True),
        ("lis2dw12", 0, False),
        ("lps22hh", 0xB1, True),
        ("lps22hh", 0xB3, True),
        ("bq25883", 3 << 3, True),
    ],
)
def test_i2c_identity(
    name: str, value: int, ok: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        sys.modules, "smbus2", SimpleNamespace(SMBus=MagicMock(), i2c_msg=Mock())
    )
    monkeypatch.setattr(i2c, "read", Mock(return_value=[value]))
    assert i2c.chip(3, name, 0x18).ok == ok


@pytest.mark.parametrize("corrupt", [False, True])
def test_sht40_checks_both_crcs(corrupt: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        sys.modules, "smbus2", SimpleNamespace(SMBus=MagicMock(), i2c_msg=Mock())
    )
    # Datasheet CRC vector: BE EF -> 92.
    assert i2c.crc8([0xBE, 0xEF]) == 0x92
    monkeypatch.setattr(
        i2c,
        "read",
        Mock(return_value=[0xBE, 0xEF, 0x92, 0xBE, 0xEF, 0 if corrupt else 0x92]),
    )
    assert i2c.chip(3, "sht40", 0x44).ok != corrupt


@pytest.mark.parametrize("running", [False, True])
def test_rtc_bits_determine_verdict_not_drift(
    running: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(i2c, "rtc_address", lambda: (1, 0x6F))
    monkeypatch.setattr(
        i2c,
        "read",
        Mock(return_value=[0x80, 0, 0, 0x28 if running else 0x08, 1, 1, 0x20]),
    )
    result = i2c.rtc_state()
    assert result.ok == running
    assert abs(result.measured["drift_s"]) > 3600


def test_failed_subprocess_probes_return_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probes, "output", Mock(side_effect=OSError("command unavailable"))
    )
    for measure in (probes.throttled, probes.nginx, probes.connect, probes.network):
        result = measure()
        assert not result.ok and result.detail


class Frame:
    ndim = 2
    dtype = "uint8"
    shape = (864, 1024)

    def __init__(self, constant: bool = False) -> None:
        self.constant = constant

    def __getitem__(self, key: object) -> "Frame":
        return self

    def __eq__(self, other: object) -> Any:
        return SimpleNamespace(mean=lambda: 0.01)

    def min(self) -> int:
        return 10

    def max(self) -> int:
        return 10 if self.constant else 250

    def mean(self) -> float:
        return 100.0


@pytest.mark.parametrize(
    "constant,exposure,gain,ok",
    [
        (False, 20000, 2.0, True),
        (True, 20000, 2.0, False),
        (False, 50000, 16.0, False),
        (False, 50000, 2.0, True),
        (False, 20000, 16.0, True),
    ],
)
def test_image_acceptance(constant: bool, exposure: int, gain: float, ok: bool) -> None:
    result = camera.frame_check(
        Frame(constant),
        {"size": (1024, 576), "format": "YUV420"},
        {"ExposureTime": exposure, "AnalogueGain": gain},
        {"ExposureTime": (1, 1000000, 20000), "AnalogueGain": (1, 16, 1)},
        Config(),
        "camera.snap",
    )
    assert result.ok == ok
    assert result.measured["saturated_frac"] == 0.01


@pytest.mark.parametrize("focus,save", [(True, True), (False, True), (True, False)])
def test_capture_keeps_image_on_focus_failure_and_releases_resources(
    focus: bool, save: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enums = SimpleNamespace(
        Normal=0, CentreWeighted=0, Auto=0, Start=1, Focused=2, Failed=3
    )
    controls = SimpleNamespace(
        **{
            name: enums
            for name in (
                "AeExposureModeEnum",
                "AeMeteringModeEnum",
                "AwbModeEnum",
                "AfModeEnum",
                "AfTriggerEnum",
                "AfStateEnum",
            )
        }
    )
    device = Mock()
    device.capture_metadata.return_value = {"AfState": 2 if focus else 3}
    device.camera_controls = {
        "ExposureTime": (1, 1000000, 20000),
        "AnalogueGain": (1, 16, 1),
    }
    device.camera_configuration.return_value = {
        "main": {"size": (1024, 576), "format": "YUV420"}
    }
    request = device.capture_request.return_value
    request.make_array.return_value = Frame()
    request.get_metadata.return_value = {
        "ExposureTime": 20000,
        "AnalogueGain": 2,
        "LensPosition": 1.5,
    }
    monkeypatch.setitem(
        sys.modules, "picamera2", SimpleNamespace(Picamera2=Mock(return_value=device))
    )
    monkeypatch.setitem(
        sys.modules, "libcamera", SimpleNamespace(Transform=Mock(), controls=controls)
    )
    converted = MagicMock()
    convert, write = Mock(return_value=converted), Mock(return_value=save)
    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(cvtColor=convert, imwrite=write, COLOR_YUV2BGR_I420=101),
    )
    monkeypatch.setitem(
        sys.modules,
        "OTCamera.module.camera.picamera2",
        SimpleNamespace(
            AWB_MODE_MAP={},
            EXPOSURE_MODE_MAP={},
            METER_MODE_MAP={},
            load_tuning_with_drc=Mock(return_value={}),
        ),
    )
    monkeypatch.setattr(camera, "sleep", lambda _: None)
    checks = camera.capture(Config(), tmp_path / "image.jpg")
    assert [(c.id, c.ok) for c in checks] == [
        ("camera.focus", focus),
        ("camera.snap", save),
    ]
    request.release.assert_called_once()
    device.close.assert_called_once()
    convert.assert_called_once_with(request.make_array.return_value, 101)
    converted.__getitem__.assert_called_once_with((slice(None, 576), slice(None, 1024)))
    assert write.called
    assert all(
        "LensPosition" not in call.args[0]
        for call in device.set_controls.call_args_list
    )


def test_report_omits_empty_fields_and_retains_failure() -> None:
    report = Report([Check("a", True, "ok"), Check("b", False, "bad", {"v": 1})])
    data = report.to_dict()
    assert data["schema"] == 1 and not data["ok"]
    assert "measured" not in data["checks"][0] and data["checks"][1]["measured"] == {
        "v": 1
    }


@pytest.mark.parametrize("bits", [0, 1, 1 << 16])
def test_historical_throttling_is_failure(
    bits: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(probes, "output", Mock(return_value=f"throttled={bits:#x}"))
    assert probes.throttled().ok == (bits == 0)


@pytest.mark.parametrize(
    "root,boot,ok",
    [
        (1_000_000_000, 100_000_000, True),
        (999_999_999, 100_000_000, False),
        (1_000_000_000, 99_999_999, False),
    ],
)
def test_free_space_boundaries(
    root: int, boot: int, ok: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        probes, "filesystem", lambda path: (0, root if path == "/" else boot)
    )
    assert probes.free().ok == ok


@pytest.mark.parametrize("root,ok", [(900, True), (899, False)])
def test_expansion_boundary(
    root: int, ok: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(probes, "output", Mock(return_value="1000"))
    monkeypatch.setattr(probes, "filesystem", lambda path: (root, 0))
    assert probes.expanded().ok == ok


@pytest.mark.parametrize("lte", [False, True])
@pytest.mark.parametrize("route", [False, True])
def test_network_primary_path_and_optional_metadata(
    lte: bool, route: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    interface = "wwan0" if lte else "wlan0"

    def output(args: list[str]) -> str:
        if "addr" in args:
            return f"{interface} UP 10.0.0.2/24"
        if "route" in args:
            return f"default via 10.0.0.1 dev {interface}" if route else ""
        if "GENERAL.CONNECTION" in args:
            return "test-network"
        raise OSError("metadata unavailable")

    monkeypatch.setattr(probes, "output", output)
    assert probes.network(lte).ok == route


def test_gnss_without_fix_passes_despite_missing_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at = Mock(side_effect=["$GPGGA,123456,,,,,0,00,99.99,,,,,,*48", OSError("no GSV")])
    monkeypatch.setattr(probes, "at", at)
    monkeypatch.setattr(probes, "output", Mock(side_effect=OSError("no mmcli")))
    result = probes.gnss_nmea()
    assert result.ok and "no fix" in result.detail
    assert "\n" not in result.detail


@pytest.mark.parametrize("enabled", [False, True])
def test_gnss_engine_is_read_only(
    enabled: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    at = Mock(return_value=f"+QGPS: {int(enabled)}")
    monkeypatch.setattr(probes, "at", at)
    assert probes.gnss_engine().ok == enabled
    at.assert_called_once_with("AT+QGPS?")


def test_system_versions_are_single_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        Path,
        "read_text",
        Mock(
            return_value="Raspberry Pi reference 2026-09-15\nGenerated using pi-gen\n"
        ),
    )
    monkeypatch.setattr(
        facts,
        "output",
        Mock(return_value="Sep 15 2026\nCopyright Raspberry Pi\nversion abc123\n"),
    )
    monkeypatch.setattr(facts, "at", Mock(side_effect=OSError("missing")))
    monkeypatch.setitem(
        sys.modules,
        "picamera2",
        SimpleNamespace(Picamera2=Mock(global_camera_info=Mock(return_value=[]))),
    )
    system = facts.collect({"provisioning": {}, "declared": {"has_lte_module": False}})[
        "system"
    ]
    assert (
        system["image"] == "Raspberry Pi reference 2026-09-15; Generated using pi-gen"
    )
    assert system["firmware"] == "Sep 15 2026; Copyright Raspberry Pi; version abc123"


@pytest.mark.parametrize(
    "driver,state,timeout,ok",
    [
        ("bcm2835-wdt", "active", "60", True),
        ("bcm2835-wdt", "inactive", "60", False),
        ("softdog", "active", "60", False),
        ("bcm2835-wdt", "active", "0", False),
        ("bcm2835-wdt", "active", "-1", False),
        ("bcm2835-wdt", "active", "invalid", False),
    ],
)
def test_watchdog_runtime_state(
    driver: str,
    state: str,
    timeout: str,
    ok: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "watchdog0"
    (root / "device").mkdir(parents=True)
    target = tmp_path / driver
    target.mkdir()
    (root / "device/driver").symlink_to(target)
    (root / "identity").write_text("Broadcom BCM2835 Watchdog timer\n")
    (root / "state").write_text(state + "\n")
    (root / "timeout").write_text(timeout + "\n")
    monkeypatch.setattr(probes, "WATCHDOG_PATH", root)
    check = probes.watchdog()
    assert check.id == "system.watchdog"
    assert check.ok is ok
    if ok:
        assert check.measured == {
            "driver": driver,
            "identity": "Broadcom BCM2835 Watchdog timer",
            "state": state,
            "timeout_s": 60,
        }


@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError])
def test_watchdog_unreadable_is_failed(
    error: type[OSError],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "resolve", Mock(side_effect=error("unavailable")))
    check = probes.watchdog()
    assert check.id == "system.watchdog" and not check.ok
    assert "unavailable" in check.detail


@pytest.mark.parametrize("has_lte", [False, True])
def test_facts_query_modem_only_when_declared(
    has_lte: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=OSError("missing")))
    monkeypatch.setattr(facts, "output", Mock(side_effect=OSError("missing")))
    monkeypatch.setitem(
        sys.modules,
        "picamera2",
        SimpleNamespace(Picamera2=Mock(global_camera_info=Mock(return_value=[]))),
    )
    uart = Mock(side_effect=["12345", "firmware", "+QCCID: 67890"])
    monkeypatch.setattr(facts, "at", uart)
    result = facts.collect(
        {"provisioning": {}, "declared": {"has_lte_module": has_lte}}
    )
    if has_lte:
        assert [args.args[0] for args in uart.call_args_list] == [
            "AT+CGSN",
            "AT+QGMR",
            "AT+QCCID",
        ]
        assert result["modem"] == {
            "imei": "12345",
            "iccid": "67890",
            "firmware": "firmware",
        }
    else:
        uart.assert_not_called()
        assert result["modem"] == {"imei": "", "iccid": "", "firmware": ""}
