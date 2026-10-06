"""Device diagnostics CLI: python -m OTCamera.diagnose."""

import argparse
import errno
import fcntl
import json
import logging
import os
import sys
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Iterator, NoReturn

from OTCamera.diagnose.report import Report, ToolError


class Parser(argparse.ArgumentParser):
    """Use the machine-readable error contract for invalid CLI arguments."""

    def error(self, message: str) -> NoReturn:
        raise ToolError(message)


def parser() -> Parser:
    """Build arguments without reading config or accessing hardware."""
    result = Parser(prog="otcamera-diagnose", description="OTCamera device diagnostics")
    result.add_argument(
        "-c",
        "--config",
        dest="config",
        type=Path,
        default=Path.home() / "user_config.yaml",
        help="Application configuration",
    )
    commands = result.add_subparsers(dest="command")
    commands.add_parser("auto", help="Run automatic checks; caller must stop OTCamera")
    commands.add_parser("facts", help="Collect device identity and provenance")
    snap = commands.add_parser(
        "snap", help="Autofocus and save a color JPEG; caller must stop OTCamera"
    )
    snap.add_argument("--out", required=True, type=Path)
    guided = commands.add_parser("guided", help="Interactive complete inspection")
    guided.add_argument("--out-dir", required=True, type=Path)
    return result


@contextmanager
def exclusive() -> Iterator[None]:
    """Refuse concurrent diagnostic invocations sharing the physical device."""
    fd = os.open(
        "/tmp/otcamera-guided.lock",
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(fd, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise ToolError("Another diagnostic inspection is running") from exc
            raise ToolError(f"Cannot acquire diagnostic lock: {exc}") from exc
        yield


def logging_policy() -> None:
    """Apply camera logging defaults before any discovery or hardware import."""
    os.environ.setdefault(
        "LIBCAMERA_LOG_LEVELS", "*:WARN,CameraSensorProperties:ERROR,CameraSensor:ERROR"
    )
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    logging.getLogger("picamera2").setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    """Emit one standalone JSON object, or run the human-readable guided flow."""
    report = Report()
    is_guided = False
    try:
        arguments = parser()
        args = arguments.parse_args(argv)
        if args.command is None:
            arguments.print_help()
            return 0
        is_guided = args.command == "guided"
        logging_policy()
        # Lazy startup keeps help independent of config and hardware libraries.
        from OTCamera.bsl.board_provider import load_board_definition
        from OTCamera.diagnose import facts
        from OTCamera.diagnose.catalog import EXPECTED_POPULATION
        from OTCamera.diagnose.provisioning import load_provisioning

        with exclusive():
            manifest = load_provisioning()
            revision = manifest["declared"]["hardware_revision"]
            board = load_board_definition(revision)
            if args.command == "facts":
                with redirect_stdout(sys.stderr):
                    result = facts.collect(manifest)
                print(json.dumps(result, allow_nan=False))
                return 0
            from OTCamera.config import parse_user_config
            from OTCamera.diagnose import automatic, camera, guided
            from OTCamera.diagnose.hardware import Hardware

            with redirect_stdout(sys.stderr):
                config_path = args.config.expanduser()
                config_path.read_bytes()
                config = parse_user_config(str(config_path))
            if (
                args.command in ("auto", "guided")
                and revision not in EXPECTED_POPULATION
            ):
                raise ToolError(
                    f"Automatic/guided inspection does not support {revision}; expected v20d"
                )
            hardware = Hardware(board)
            if is_guided:
                return guided.inspect(
                    config, manifest, hardware, args.out_dir.expanduser()
                )
            try:
                with redirect_stdout(sys.stderr):
                    if args.command == "auto":
                        report.checks.extend(
                            automatic.inspect(
                                config,
                                revision,
                                manifest["declared"]["has_lte_module"],
                                hardware,
                            )
                        )
                    else:
                        report.checks.extend(
                            camera.capture(config, args.out.expanduser())
                        )
            finally:
                hardware.close()
                if hardware.cleanup_errors:
                    report.error = "; ".join(hardware.cleanup_errors)
        print(json.dumps(report.to_dict(), allow_nan=False))
        return 2 if report.error else 0 if report.ok else 1
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        report.error = str(exc)
        if is_guided:
            print(f"Inspection error: {exc}", file=sys.stderr)
        else:
            print(json.dumps(report.to_dict(), allow_nan=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
