"""Artifacts, independent areas, service handling and failure cleanup."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from OTCamera.bsl.board_provider import load_board_definition
from OTCamera.config import Config
from OTCamera.diagnose import guided as g
from OTCamera.diagnose.automatic import inspect as automatic_checks
from OTCamera.diagnose.report import Check, ToolError


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock, Mock]:
    monkeypatch.setattr(g.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(g.sys.stdout, "isatty", lambda: True)
    terminal = Mock()
    monkeypatch.setattr(g, "Terminal", Mock(return_value=terminal))
    hardware = Mock()
    hardware.buttons = {"power": object()}
    hardware.cleanup_errors = []
    hardware.switches.return_value = (True,) * 4
    service = Mock()
    monkeypatch.setattr(g, "service", service)
    monkeypatch.setattr(
        g,
        "output",
        Mock(
            side_effect=lambda args: "active" if args[1] == "is-active" else "enabled"
        ),
    )
    monkeypatch.setattr(
        g.facts,
        "collect",
        Mock(
            return_value={"schema": 1, "device": {"hostname": "test", "serial": "123"}}
        ),
    )
    monkeypatch.setattr(
        g.automatic,
        "inspect",
        Mock(return_value=[Check(f"auto.{i}", True, "ok") for i in range(19)]),
    )
    monkeypatch.setattr(g, "ui", Mock(return_value=Check("ui", True, "ok")))
    monkeypatch.setattr(
        g, "power", Mock(return_value=Check("power.switchover", True, "ok"))
    )

    def capture(config: Config, image: Path) -> list[Check]:
        image.write_bytes(b"image")
        return [Check("camera.focus", True, "ok"), Check("camera.snap", True, "ok")]

    monkeypatch.setattr(g.camera, "capture", capture)
    return hardware, service, terminal


def run(path: Path, hardware: Mock) -> int:
    return g.inspect(
        Config(),
        {"declared": {"hardware_revision": "v20d", "has_lte_module": False}},
        hardware,
        path,
    )


@pytest.mark.parametrize("ui_ok", [True, False])
def test_complete_run_and_independent_power(
    ui_ok: bool,
    session: tuple[Mock, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hardware, service, terminal = session
    monkeypatch.setattr(g, "ui", Mock(return_value=Check("ui", ui_ok, "UI result")))
    power = Mock(return_value=Check("power.switchover", True, "ok"))
    monkeypatch.setattr(g, "power", power)
    directory = tmp_path / "inspection"
    assert run(directory, hardware) == (0 if ui_ok else 1)
    protocol = json.loads((directory / "protocol.json").read_text())
    manifest = json.loads((directory / "manifest.json").read_text())
    assert protocol["status"] == "completed" and protocol["result"] == (
        "passed" if ui_ok else "failed"
    )
    assert len(protocol["checks"]) == 24
    assert protocol["run_id"] == directory.name
    assert "qa" not in manifest
    assert (directory / "testpattern.jpg").read_bytes() == b"image"
    assert not list(directory.glob("*.tmp"))
    power.assert_called_once()
    hardware.switches.assert_not_called()
    assert [c.args[0] for c in service.call_args_list] == ["stop"]
    hardware.close.assert_called_once()
    assert terminal.close.called




@pytest.mark.parametrize(
    "error,code",
    [(EOFError("EOF"), 2), (KeyboardInterrupt(), 130), (RuntimeError("hardware"), 2)],
)
def test_abort_preserves_partial_protocol_and_stops_service(
    error: BaseException,
    code: int,
    session: tuple[Mock, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hardware, service, terminal = session
    monkeypatch.setattr(g, "ui", Mock(side_effect=error))
    directory = tmp_path / "aborted"
    assert run(directory, hardware) == code
    protocol = json.loads((directory / "protocol.json").read_text())
    assert protocol["status"] == "aborted" and protocol["result"] == "incomplete"
    assert protocol["checks"] and protocol["error"]
    assert [c.args[0] for c in service.call_args_list] == ["stop", "stop"]
    hardware.close.assert_called_once()
    terminal.close.assert_called_once()


def test_cleanup_failure_leaves_service_stopped(
    session: tuple[Mock, Mock, Mock], tmp_path: Path
) -> None:
    hardware, service, _ = session
    hardware.close.side_effect = lambda: hardware.cleanup_errors.append(
        "release failed"
    )
    directory = tmp_path / "cleanup"
    assert run(directory, hardware) == 2
    protocol = json.loads((directory / "protocol.json").read_text())
    assert (
        protocol["result"] == "incomplete"
        and "release failed" in protocol["cleanup_error"]
    )
    assert all(c.args[0] == "stop" for c in service.call_args_list)


def test_missing_image_fails_even_if_capture_claims_success(
    session: tuple[Mock, Mock, Mock], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hardware, _, _ = session
    monkeypatch.setattr(
        g.camera,
        "capture",
        Mock(
            return_value=[
                Check("camera.focus", True, "ok"),
                Check("camera.snap", True, "ok"),
            ]
        ),
    )
    assert run(tmp_path / "missing-image", hardware) == 1


@pytest.mark.parametrize("existing", [True, False])
def test_preconditions_do_not_touch_service(
    existing: bool,
    session: tuple[Mock, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hardware, service, _ = session
    directory = tmp_path / "precondition"
    if existing:
        directory.mkdir()
    else:
        monkeypatch.setattr(g.sys.stdout, "isatty", lambda: False)
    with pytest.raises(ToolError):
        run(directory, hardware)
    service.assert_not_called()


def test_checkpoint_failure_leaves_service_stopped(
    session: tuple[Mock, Mock, Mock], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hardware, service, _ = session
    save = g.save

    def fail_final(path: Path, value: dict[str, Any]) -> None:
        if value.get("status") == "completed":
            raise OSError("disk full")
        save(path, value)

    monkeypatch.setattr(g, "save", fail_final)
    directory = tmp_path / "disk-full"
    with pytest.raises(ToolError, match="Cannot finalize"):
        run(directory, hardware)
    assert [c.args[0] for c in service.call_args_list] == ["stop", "stop"]
    assert json.loads((directory / "protocol.json").read_text())["status"] == "aborted"


def test_incomplete_checks_cannot_be_published_as_completed(
    session: tuple[Mock, Mock, Mock], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hardware, service, _ = session
    monkeypatch.setattr(g.automatic, "inspect", Mock(return_value=[]))
    directory = tmp_path / "missing-checks"
    assert run(directory, hardware) == 2
    protocol = json.loads((directory / "protocol.json").read_text())
    assert protocol["status"] == "aborted" and protocol["result"] == "incomplete"
    assert service.call_args.args == ("stop",)


@pytest.mark.parametrize("lte", [False, True])
def test_guided_accepts_actual_automatic_check_count(
    lte: bool,
    session: tuple[Mock, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hardware, _, _ = session
    hardware.board = load_board_definition("v20d")
    monkeypatch.setattr(g.automatic, "inspect", automatic_checks)
    monkeypatch.setattr(
        g.automatic, "_check", Mock(side_effect=lambda check_id, *a, **kw: Check(check_id, True, "ok"))
    )
    code = g.inspect(
        Config.model_validate({"hardware": {"pcb_version": "v20d"}}),
        {"declared": {"hardware_revision": "v20d", "has_lte_module": lte}},
        hardware,
        tmp_path / "inspection",
    )
    protocol = json.loads((tmp_path / "inspection/protocol.json").read_text())
    # The host may lack /dev/i2c; that is a check failure, never an aborted run.
    assert code in (0, 1)
    assert protocol["status"] == "completed"
    assert len(protocol["checks"]) == (28 if lte else 24)
    assert "system.watchdog" in {check["id"] for check in protocol["checks"]}


@pytest.mark.parametrize("abort", [False, True])
def test_automatic_output_is_deferred_but_checkpointed(
    abort: bool,
    session: tuple[Mock, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hardware, _, _ = session
    directory = tmp_path / "deferred"
    monkeypatch.setattr(g.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(g.sys.stdin, "isatty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")

    def guided_ui(*args: Any) -> Check:
        before = capsys.readouterr().out
        assert "Automatic checks complete." in before
        assert "PASS auto." not in before
        assert "AUTOMATIC CHECKS" not in before
        protocol = json.loads((directory / "protocol.json").read_text())
        assert len(protocol["checks"]) == 19
        if abort:
            raise KeyboardInterrupt()
        return Check("ui", True, "ok")

    monkeypatch.setattr(g, "ui", guided_ui)
    assert run(directory, hardware) == (130 if abort else 0)
    after = capsys.readouterr().out
    assert after.count("AUTOMATIC CHECKS") == 1
    for index in range(19):
        assert after.count(f"PASS auto.{index}: ok") == 1
    assert after.index("AUTOMATIC CHECKS") < after.index("Inspection ")
    if not abort:
        assert after.index("power.switchover:") < after.index("AUTOMATIC CHECKS")
        assert after.index("PASS auto.18: ok") < after.index("CAMERA CHECK")
