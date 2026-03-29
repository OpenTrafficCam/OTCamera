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

## Code Conventions

### General

- Type-annotate all function signatures (parameters + return type), including private helpers.
- Google-style docstrings on all public functions, classes, and modules.
- No wildcard imports (`from foo import *`).
- Raise specific exception types; never bare `except:` or `except Exception:` without re-raising or logging.
- Prefer `pathlib.Path` over `os.path` for file operations.
- Use `logging` (not `print`) for any diagnostic output in library code.

### Naming

| Construct       | Convention         | Example                  |
|-----------------|--------------------|--------------------------|
| Module          | `snake_case`       | `data_loader.py`         |
| Class           | `PascalCase`       | `DataLoader`             |
| Function/method | `snake_case`       | `load_records()`         |
| Constant        | `UPPER_SNAKE_CASE` | `MAX_RETRIES = 3`        |
| Private         | leading underscore | `_internal_helper()`     |
| Type alias      | `PascalCase`       | `RecordList = list[...]` |

Beyond casing, names must follow these Clean Code rules:

- **Intention-revealing:** names must explain *what* and *why*, not *how*. Avoid abbreviations and
  single-letter names except for conventional loop counters (`i`, `j`).
  `elapsed_time_in_days` not `d`; `is_flagged_for_deletion` not `flag`.
- **No encodings:** no Hungarian notation, no type prefixes, no redundant context.
  `User.name` not `User.user_name`; `count` not `int_count`.
- **Pronounceable:** names must be speakable. `generation_timestamp` not `gen_ymdhms`.
- **Searchable:** never use bare magic numbers or magic strings in non-trivial code — extract them
  into named constants so they can be searched and changed in one place.
  `MAX_POLL_INTERVAL_SECONDS = 5` not a bare `5` scattered through the code.

### Clean Code

#### Functions and methods

- **Do one thing:** a function must have a single, clearly nameable purpose at one level of
  abstraction. If you can extract a sub-function with a meaningful name that is not merely a
  restatement of the function itself, do it.
- **One level of abstraction per function:** do not mix high-level orchestration with low-level
  detail in the same function body.
- **Prefer fewer arguments:** aim for 0–2 parameters. Three is acceptable with justification. More
  than three is a smell — consider grouping related parameters into a dataclass or value object.
- **No hidden side effects:** a function must do exactly what its name says and nothing more. Hidden
  state mutations that are not reflected in the function name are forbidden.

#### Classes

- **Single Responsibility Principle:** a class has exactly one reason to change. If you describe its
  purpose using the word "and", it should be split into two classes.
- **Small classes:** keep classes small. A class growing beyond ~200 lines is a signal to reconsider
  its responsibilities.
- **Law of Demeter:** talk only to direct collaborators. Avoid method-call chains that traverse
  object graphs: `obj.get_a().get_b().do_c()` means your code knows too much about internal
  structure. Introduce a method on the intermediate object instead.
- **Tell, don't ask:** do not query an object's state to decide what to do with it externally —
  tell the object to do it. Querying state to branch on it is a sign the logic belongs inside the
  object.

#### Comments

- **Prefer self-documenting code over comments.** If a comment is needed to explain *what* code
  does, rename or extract until the code speaks for itself. Comments explain *why* — the intent,
  trade-off, or constraint that cannot be expressed in code.
- **No commented-out code.** Dead code must be deleted, not commented out. Version control preserves
  history.
- **No redundant comments.** A comment that merely restates the code (`# increment i` above `i += 1`)
  adds noise and must be removed.

#### Constants and duplication

- Extract every magic number and magic string into a named constant at the top of the module or
  class. Constants are `UPPER_SNAKE_CASE`.
- Apply DRY (Don't Repeat Yourself): if the same logic or value appears in two places, extract it.
  Duplication is the root of maintenance problems.

### Imports

Sort order (enforced by `isort --profile black`):

1. Standard library
2. Third-party packages
3. Local (`from OTCamera import ...`)

### Line length

Max 88 characters (Black default). Strings and comments may exceed this only when breaking them would reduce
readability.

---
## What to Check When Implementing a Change

Work through this list before considering an implementation complete.

### Correctness

- [ ] Does the change fully satisfy the issue's acceptance criteria?
- [ ] Are all edge cases handled (empty input, `None`, zero, very large values, Unicode)?
- [ ] Does error handling preserve useful context (error messages, original exceptions via `raise ... from`)?
- [ ] Are any assumptions about input documented via assertions or docstrings?

### API & Compatibility

- [ ] Does the change preserve the existing public API? If not, is a deprecation warning added?
- [ ] Are new public symbols exported in `__init__.py` if appropriate?

### Types

- [ ] Do all new functions have complete type annotations?

### Tests

- [ ] Do all existing tests still pass?
- [ ] Are new tests added for the changed behaviour?
- [ ] Is test coverage maintained or improved?

### Documentation

- [ ] Do new/changed functions have accurate docstrings?
- [ ] If the public API changed, is `docs/` updated?

### Security

- [ ] Does the change handle untrusted input safely (no shell injection, path traversal, unsafe deserialization)?
- [ ] Are secrets, tokens, or credentials never hardcoded or logged?
- [ ] Are new dependencies pinned/vetted? Prefer stdlib or already-used packages.

### Performance

- [ ] Does the change introduce any O(n²) or worse operations on unbounded input?
- [ ] Are file handles, database connections, and network sessions closed properly (use `with` blocks)?

---

## What a Reviewer Agent Should Check

If you are acting as a **code reviewer** rather than an implementer, verify the following for every PR diff.

### Must-block (do not approve if any of these fail)

- Tests are absent for new or changed behaviour.
- `mypy` or `flake8` errors exist anywhere in the diff.
- Public API is broken without a deprecation path.
- Secrets, tokens, or credentials appear in code or tests.
- Bare `except:` swallows errors silently.
- Untrusted input is passed to `subprocess`, `eval`, `exec`, or `os.system`.
- New heavyweight dependency added without justification.
- A regression test is missing for a bugfix.

### Should-flag (leave a comment, but may still approve)

- Function is longer than ~50 lines without a clear reason.
- Logic is duplicated instead of extracted into a helper.
- A `TODO` or `FIXME` is left without a linked issue.
- `# type: ignore` or `# noqa` is used without explanation.
- A test asserts on implementation details rather than observable behaviour.
- Log messages expose sensitive data (user IDs, emails, internal paths).
- A docstring is missing on a public function introduced in this PR.

### Positive signals (acknowledge these)

- Edge cases are covered with parametrized tests.
- Complex logic has an explanatory comment linking to the relevant issue or spec.
- Deprecation is handled cleanly with a `DeprecationWarning` and a target version.

---

## Out of Scope for Agents

Do **not** do the following without explicit human instruction:

- Bump dependency versions in `pyproject.toml` or `requirements*.txt`
- Change CI/CD pipeline files (`.github/workflows/`)
- Alter license or copyright headers
- Refactor files unrelated to the current task
- Push directly to `main` or `develop` or `master` — always use a branch + PR