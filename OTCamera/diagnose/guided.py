"""Straight-line guided inspection and atomic, compact artifact checkpoints."""

import json
import os
import signal
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from socket import gethostname
from types import FrameType
from typing import Any

from OTCamera.config import Config
from OTCamera.diagnose import automatic, camera, facts
from OTCamera.diagnose.hardware import Hardware
from OTCamera.diagnose.interaction import Terminal, color, power, section, ui
from OTCamera.diagnose.report import Check, ToolError, output


def timestamp() -> str:
    """Return a timezone-qualified UTC timestamp with ordering precision."""
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, value: dict[str, Any]) -> None:
    """Checkpoint through replacement on the same filesystem."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def service(action: str) -> None:
    """Perform the only privileged operations permitted by this tool."""
    output(["sudo", "-n", "systemctl", action, "otcamera.service"], timeout=30)


def _interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt(f"Interrupted by signal {signum}")


def inspect(
    config: Config, manifest: dict[str, Any], hardware: Hardware, out: Path
) -> int:
    """Run the complete guided lifecycle, retaining partial artifacts on abort."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ToolError("guided requires a terminal on stdin and stdout")
    if out.exists() or not out.parent.is_dir():
        raise ToolError("Output directory must be new and its parent must exist")
    out.mkdir(mode=0o700)
    protocol: dict[str, Any] = {
        "schema": 1,
        "run_id": out.name,
        "host": gethostname(),
        "started": timestamp(),
        "finished": None,
        "status": "running",
        "result": "incomplete",
        "checks": [],
    }
    protocol_path = out / "protocol.json"
    terminal = Terminal()
    touched = False
    released = False
    exit_code = 2
    handlers: dict[signal.Signals, Any] = {}
    automatic_results: list[Check] = []

    def display(check: Check) -> None:
        verdict = color("PASS", "32") if check.ok else color("FAIL", "31")
        sys.stdout.write(f"{verdict} {check.id}: {check.detail}\n")
        sys.stdout.flush()

    def display_automatic() -> None:
        if automatic_results:
            section("AUTOMATIC CHECKS")
            for check in automatic_results:
                display(check)
            automatic_results.clear()

    def record(check: Check, *, deferred: bool = False) -> None:
        value = asdict(check)
        if not value["measured"]:
            del value["measured"]
        protocol["checks"].append(value)
        save(protocol_path, protocol)
        if deferred:
            automatic_results.append(check)
        else:
            display(check)

    try:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            handlers[sig] = signal.signal(sig, _interrupt)
        save(protocol_path, protocol)
        touched = True
        service("stop")
        identity = facts.collect(manifest)
        save(out / "manifest.json", identity)
        declared = manifest["declared"]
        for check in automatic.inspect(
            config, declared["hardware_revision"], declared["has_lte_module"], hardware
        ):
            record(check, deferred=True)
        sys.stdout.write("Automatic checks complete.\n")
        sys.stdout.flush()
        terminal.open()
        section("GUIDED CHECKS")
        sys.stdout.write("X = fail current area    Ctrl-C = abort\n")
        record(ui(hardware, terminal))
        section("POWER CHECK")
        record(power(hardware, terminal, config))
        terminal.close()
        terminal.previous = None
        display_automatic()
        section("CAMERA CHECK")
        image = out / "testpattern.jpg"
        for check in camera.capture(config, image):
            record(check)
        record(
            Check(
                "camera.artifact",
                image.is_file() and image.stat().st_size > 0,
                "Nonempty testpattern.jpg"
                if image.is_file() and image.stat().st_size > 0
                else "Missing or empty testpattern.jpg",
            )
        )
        hardware.close()
        released = True
        if hardware.cleanup_errors:
            raise ToolError("Hardware cleanup failed")
        expected_count = (23 if declared["has_lte_module"] else 19) + 5
        if len(protocol["checks"]) != expected_count:
            raise ToolError("Inspection did not produce all required checks")
        passed = all(c["ok"] for c in protocol["checks"])
        protocol.update(status="completed", result="passed" if passed else "failed")
        exit_code = 0 if passed else 1
    except KeyboardInterrupt as exc:
        protocol.update(
            status="aborted", result="incomplete", error=str(exc) or "Interrupted"
        )
        exit_code = 130
    except Exception as exc:
        protocol.update(status="aborted", result="incomplete", error=str(exc))
        exit_code = 2
    finally:
        # Do not let a second interrupt strand resources during cleanup.
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        cleanup = hardware.cleanup_errors
        try:
            terminal.close()
        except Exception as exc:
            cleanup.append(f"Terminal restore: {exc}")
        if not released:
            hardware.close()
        if touched and protocol["status"] != "completed":
            try:
                service("stop")
            except Exception as exc:
                cleanup.append(f"Service stop: {exc}")
        if cleanup:
            protocol["cleanup_error"] = "; ".join(cleanup)
            protocol["result"] = (
                "failed" if protocol["status"] == "completed" else "incomplete"
            )
            if exit_code != 130:
                exit_code = 2
        protocol["finished"] = timestamp()
        try:
            save(protocol_path, protocol)
        except Exception as exc:
            protocol.update(
                status="aborted", result="incomplete", error=f"Final checkpoint: {exc}"
            )
            if touched:
                try:
                    service("stop")
                except Exception as stop_error:
                    protocol["cleanup_error"] = f"Service stop: {stop_error}"
            try:
                save(protocol_path, protocol)
            except Exception:
                pass
            raise ToolError(f"Cannot finalize inspection protocol: {exc}") from exc
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
            display_automatic()
    sys.stdout.write(f"Inspection {protocol['status']}: {protocol['result']} — {out}\n")
    return exit_code
