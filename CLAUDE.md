# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OTCamera is a Raspberry Pi Zero W-based video recording system for traffic monitoring, part of the [OpenTrafficCam](https://github.com/OpenTrafficCam) framework. It records multi-day h264 video with configurable intervals, serves a status website over Wi-Fi AP, and supports hardware buttons/LEDs, FTP upload, ADC power monitoring, and MS Teams notifications.

**Target platform:** Raspberry Pi Zero W (Python >=3.9). Hardware-dependent modules (`picamerax`, `picamera2`, `gpiozero`, `RPi.GPIO`) will fail to import on non-Pi systems. `RPi.GPIO` is excluded from install on Windows/macOS via platform markers.

**Branch:** `v2` — adds picamera2 support, PCB v2 hardware revision with new pin mappings, ADC-based power monitoring, and abstract domain interfaces for camera/LED/ADC.

## Commands

### Setup
```bash
bash install.sh              # create venv (Python 3.9), install runtime deps
bash install_dev.sh          # install.sh + dev deps + editable install + pre-commit hooks
```

### Run
```bash
python run.py                          # default config: ~/user_config.yaml
python run.py -c /path/to/config.yaml  # custom config
python -m OTCamera                     # alternative entry
```

### Tests
```bash
pytest                                 # all tests
pytest tests/helpers/name_test.py      # single test file
pytest -k "test_function_name"         # single test by name
pytest --cov                           # with coverage
```

### Linting & Formatting
Pre-commit runs all checks on commit. Manual:
```bash
pre-commit run --all-files
black .                                # formatting (line length 88)
isort .                                # import sorting (black profile)
flake8                                 # linting (google docstrings, extend-ignore E203)
mypy OTCamera tests --config-file=pyproject.toml  # type checking (disallow_untyped_defs)
```

### CI
GitHub Actions runs super-linter on PRs (flake8, isort, yamllint). Pre-commit hooks additionally run mypy, shellcheck, shfmt, and auto type-stub updates.

## Architecture

### Entry Points
- `run.py` — Parses CLI args, loads YAML config. If USB device is present, copies videos to USB; otherwise starts recording via `OTCamera.record`.
- `OTCamera/__main__.py` — Alternate entry, directly calls `record()`.

### Key Modules (`OTCamera/`)

- **`config.py`** — Global configuration as module-level variables. `parse_user_config()` reads YAML and overwrites globals via `setattr`. Supports `camera.type: legacy|picamera2` to select camera backend. PCB version (`hardware.pcb_version: v1|v2`) determines GPIO pin mappings.
- **`status.py`** — Global runtime state (recording status, button states, wifi, intervals).
- **`record.py`** — Core `OTCamera` class: recording loop, video splitting at intervals, preview capture, signal-based shutdown, disk space management.
- **`html_updater.py`** — BeautifulSoup-based status website updater with dataclass DTOs.

### Domain Layer (`domain/`)
Abstract interfaces for hardware, no framework dependencies:
- `camera.py` — Abstract `Camera` ABC with type literals (`H264Profile`, `H264Level`, `VideoFormat`)
- `camera_errors.py` — `CameraClosedError`
- `adc.py` — Abstract `ADC` ABC for voltage readings

### Hardware & Plugins
- **`hardware/`** — Pi hardware control: `camera_controller.py`, `button.py`, `led.py`, `power_controller.py`
- **`plugin/camera/`** — Camera backends: `picamerax.py` (legacy), `picamera2.py` (new). `camera_provider.py` selects based on config.
- **`plugin/adc/`** — ADC implementations: `tla2024.py` (TI TLA2024 I2C ADC). `adc_provider.py` selects implementation.
- **`plugin_ftp_server/`** — FTP/FTPS video upload
- **`helpers/`** — `log.py`, `name.py` (filename generation), `filesystem.py` (disk space, cleanup), `rpi.py` (system commands)
- **`abstraction/singleton.py`** — Singleton pattern base class (used by Camera)

### Test Structure (`tests/`)
- `tests/helpers/` — `name_test.py`, `filesystem_test.py`
- `tests/hardware/` — `camera_test.py`
- `tests/domain/` — domain layer tests
- Test files use `_test.py` suffix (legacy) or `test_` prefix (domain)
- Shared fixtures in `conftest.py`: `test_dir` (auto-cleaned temp dir), `resources_dir`
- `hardware_test.py` (root) — standalone Pi hardware verification script, not a pytest test

### Configuration
YAML file (see `user_config.example.yaml`). Key sections: debug_mode, recording (hours/intervals), camera (fps/resolution/type), preview, video (encoder settings), wifi, leds, buttons, hardware (pcb_version), msteams, adc.

### Build System
Hatch (hatchling) via `pyproject.toml`. Version from `OTCamera/version.py`. Dependencies from `requirements.txt` via `hatch-requirements-txt` plugin.

### Conventions
- Black (88 chars), isort (black profile), flake8 (google docstrings)
- mypy with `disallow_untyped_defs = true` (html_updater modules excluded)
- GPL-3.0 license header in all source files
- Default branch: `master`
