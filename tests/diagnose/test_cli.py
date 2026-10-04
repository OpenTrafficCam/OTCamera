"""Public CLI, JSON and locking contracts without camera access."""

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from OTCamera.diagnose import __main__ as cli
from OTCamera.diagnose import automatic, camera, facts, provisioning
from OTCamera.diagnose.report import Check, ToolError


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    manifest = tmp_path / "provisioning.yml"
    manifest.write_text(
        "provisioning: {}\ndeclared: {hardware_revision: v20d, has_lte_module: false}\n"
    )
    monkeypatch.setattr(provisioning, "PROVISIONING_PATH", manifest)
    path = tmp_path / "config.yml"
    path.write_text("hardware: {pcb_version: v20d}\n")
    return path


@pytest.mark.parametrize("args", [[], ["--help"], ["-c", "/missing"]])
def test_help_needs_no_configuration(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(args) == 0
    assert "{auto,facts,snap,guided}" in capsys.readouterr().out


@pytest.mark.parametrize(
    "args", [["read"], ["set"], ["snap"], ["guided"], ["auto", "--expect-lte"]]
)
def test_invalid_arguments_are_json(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(args) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == 1 and not result["ok"] and result["error"]


@pytest.mark.parametrize("option", ["-c", "--config"])
@pytest.mark.parametrize("ok", [True, False])
def test_automatic_json_and_exit_status(
    option: str,
    ok: bool,
    config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    measure = Mock(return_value=iter([Check("example", ok, "result")]))
    monkeypatch.setattr(automatic, "inspect", measure)
    assert cli.main([option, str(config), "auto"]) == (0 if ok else 1)
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] == ok and result["checks"] == [
        {"id": "example", "ok": ok, "detail": "result"}
    ]
    assert measure.call_args.args[1:3] == ("v20d", False)


def test_missing_config_is_error(
    config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config.unlink()
    assert cli.main(["-c", str(config), "auto"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]


def test_facts_ignore_config(
    config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    collect = Mock(return_value={"schema": 1, "device": {"hostname": "test"}})
    monkeypatch.setattr(facts, "collect", collect)
    assert cli.main(["--config", "/missing", "facts"]) == 0
    assert json.loads(capsys.readouterr().out)["device"]["hostname"] == "test"
    assert collect.call_args.args[0]["declared"]["hardware_revision"] == "v20d"


def test_snap_dispatch(
    config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    capture = Mock(
        return_value=[
            Check("camera.focus", False, "focus failed"),
            Check("camera.snap", True, "saved"),
        ]
    )
    monkeypatch.setattr(camera, "capture", capture)
    assert cli.main(["-c", str(config), "snap", "--out", "image.jpg"]) == 1
    assert capture.call_args.args[1] == Path("image.jpg")
    assert len(json.loads(capsys.readouterr().out)["checks"]) == 2


def test_lock_matches_wrapper_and_excludes_readers() -> None:
    with cli.exclusive():
        with pytest.raises(ToolError):
            with cli.exclusive():
                pass
        with Path(f"/tmp/otcamera-guided-{os.getuid()}.lock").open() as guard:
            with pytest.raises(BlockingIOError):
                fcntl.flock(guard, fcntl.LOCK_SH | fcntl.LOCK_NB)
    with cli.exclusive():
        pass


def test_help_imports_no_hardware_or_config() -> None:
    script = "from OTCamera.diagnose.__main__ import main; import sys; assert main([]) == 0; assert not {'gpiozero', 'picamera2', 'smbus2', 'OTCamera.config'} & sys.modules.keys()"
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr


def test_logging_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIBCAMERA_LOG_LEVELS", raising=False)
    cli.logging_policy()
    assert (
        os.environ["LIBCAMERA_LOG_LEVELS"]
        == "*:WARN,CameraSensorProperties:ERROR,CameraSensor:ERROR"
    )
    monkeypatch.setenv("LIBCAMERA_LOG_LEVELS", "*:DEBUG")
    cli.logging_policy()
    assert os.environ["LIBCAMERA_LOG_LEVELS"] == "*:DEBUG"
