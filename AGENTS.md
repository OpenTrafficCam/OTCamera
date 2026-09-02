<!-- @generated -->

# AGENTS.md

This file provides guidance to coding agents working in this repository.

## Project Overview

OTCamera is a Raspberry Pi Zero W-based video recording system for traffic
monitoring, part of the
[OpenTrafficCam](https://github.com/OpenTrafficCam) framework. It records
multi-day h264 video with configurable intervals, serves a status website over
Wi-Fi AP, and supports hardware buttons and LEDs, FTP upload, ADC power
monitoring, and MS Teams notifications.

Target platform: Raspberry Pi OS Bookworm/Trixie on Raspberry Pi Zero W
(`Python >=3.12`; Bookworm ships 3.12, Trixie ships 3.13). Hardware-dependent
modules such as `picamera2`, `gpiozero`, and `smbus2` will fail to import on
non-Pi systems.

Primary working branch for this refactor: `v2-refactor`.

See [`docs/dev.md`](docs/dev.md) for the human-facing developer setup and testing guide.

## Commands

### Setup

```bash
bash install.sh
bash install_dev.sh
```

### Run

```bash
python run.py
python run.py -c /path/to/config.yaml
python -m OTCamera
python hardware_check.py
```

All standardized tasks run through [`just`](https://github.com/casey/just).
Use the recipes below instead of invoking `pytest`, `ruff`, `mypy`, or
`super-linter` directly, so agents and CI use identical commands and options.
Run `just` (the default recipe) to list the available recipes.

### Tests

```bash
just test-unit   # unit tests only (pytest -m 'not integration')
just test        # full suite; starts and awaits the container dependencies
```

Container lifecycle for the integration tests is handled by the recipes
`start-containers`, `stop-containers`, `wait-rabbitmq`, and `wait-rustfs`;
`just test` already depends on them.

To narrow a run, append pytest arguments to the underlying recipe command
rather than switching to a bare `pytest` call:

```bash
uv run pytest -m 'not integration' tests/test_config.py
uv run pytest -m 'not integration' -k "test_function_name"
```

### Linting and Type Checking

```bash
just lint        # ruff check
just fix         # ruff check --fix
just format      # ruff format
just typecheck   # mypy OTCamera tests
just super-lint  # super-linter in Docker, mirrors the CI stage
```

Never call `ruff`, `black`, `isort`, `flake8`, or `mypy` by hand — always go
through the recipes above. The same checks also run as pre-commit hooks:

```bash
pre-commit run --all-files
```

## Architecture

### Entry Points

- `run.py` loads YAML config, chooses recorder or USB-copy mode, and starts the
  application.
- `OTCamera/__main__.py` is the composition root for recorder mode.
- `usb_flash_drive_copy.py` contains the USB export path.
- `hardware_check.py` is the standalone hardware verification script.

### Layering

- `OTCamera/domain/`: stable domain contracts and events.
- `OTCamera/bsl/`: board support layer for concrete Pi hardware access.
- `OTCamera/module/`: pluggable hardware-backed modules such as the camera.
- `OTCamera/plugin/`: pluggable software integrations such as upload backends.
- `OTCamera/controller/`: application logic orchestrating the domain contracts.

### Domain Layer

The `domain` package contains abstract interfaces and event types that do not
depend on concrete libraries:

- `camera.py`: `Camera` ABC and camera-related exceptions.
- `adc.py`: `ADC` ABC, `ADCConfig`, and ADC exceptions.
- `led.py`: `LED` ABC.
- `button.py`: `Button` ABC.
- `upload.py`: `Upload` ABC.
- `events.py`: hybrid event bus and typed event dataclasses.

### Providers and Implementations

- `OTCamera/bsl/board_provider.py` builds concrete LEDs, buttons, and ADC
  objects from the board definition and injected config.
- `OTCamera/module/camera/camera_provider.py` builds the active camera module.
- `OTCamera/plugin/upload/upload_provider.py` builds the upload backend.

Concrete implementations live below those provider packages, for example:

- `OTCamera/bsl/led/pwm_led.py`
- `OTCamera/bsl/button/gpio_button.py`
- `OTCamera/bsl/adc/tla2024.py`
- `OTCamera/module/camera/picamera2.py`
- `OTCamera/plugin/upload/ftp_upload.py`

### Main Runtime Flow

`OTCamera/__main__.py` wires together config, logging, event bus, providers, and
controllers. The main loop:

1. processes queued GPIO events,
2. checks power and Wi-Fi state,
3. updates schedule and recording state,
4. captures preview and status output,
5. handles shutdown cleanup.

### Important Design Decisions

- Config is injected as a dataclass, not read from a global singleton.
- Controllers depend on domain contracts, not concrete hardware classes.
- GPIO callbacks enqueue events; main-thread application logic publishes events
  synchronously on the hybrid event bus.
- Board-specific pin mappings live in `OTCamera/bsl/boards/`.

## Tests

Primary test areas:

- `tests/domain/`
- `tests/bsl/`
- `tests/controller/`
- `tests/hardware/`
- `tests/test_config.py`
- `tests/html_updater_test.py`

Pytest test discovery is configured in `pyproject.toml` via `testpaths =
["tests"]`.

## Coding Conventions

### General

- Type-annotate all function signatures, including private helpers.
- Use Google-style docstrings on public modules, classes, and functions.
- No wildcard imports (`from x import *`).
- Import only what is needed: prefer `from module import Name` over importing the whole module when only specific names are used.
- Raise specific exceptions and preserve context with `raise ... from`.
- Prefer `pathlib.Path` over `os.path`.
- Use `logging`, not `print`, in library code.

### Clean Code

- Keep functions focused on one level of abstraction.
- Prefer explicit dependencies over hidden globals.
- Keep classes small and responsibility-focused.
- Prefer self-documenting code over explanatory comments.
- Extract repeated values into named constants.

### Review Expectations

Before considering work complete:

- run the relevant tests via `just test-unit` (or `just test`),
- keep `just lint` and `just typecheck` clean in touched code,
- add regression tests for bug fixes,
- avoid shell injection and unsafe subprocess use,
- update docs if public behavior or architecture changes,
- update `user_config.yaml` and `user_config.example.yaml` whenever fields are
  added to or removed from the `Config` model in `OTCamera/config.py`.
