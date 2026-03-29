# OTCamera v2 Architecture Refactor — Design

**Date:** 2026-03-05
**Updated:** 2026-03-27 (consolidated with hardware layer separation amendment, applied learnings from first implementation attempt, design review refinements)
**Branch:** `v2-refactor` (from `v2`)
**Status:** Approved

## Context

OTCamera v2 targets new hardware: RPi Zero W2, RPi Camera Module v3, PCB v2, Raspi OS Trixie. The codebase needs a clean architecture that allows swapping hardware components (camera, ADC, LEDs, buttons, GPS, LTE, accelerometer) without refactoring core logic. Upcoming features include a web UI, message broker integration, GPS, LTE, and accelerometer support.

**Target platform:** Python >=3.11 on Raspberry Pi Zero W2 (Bookworm ships 3.12, Trixie ships 3.13).

Modern Python syntax (`X | Y`, `tuple[int, int]`, `match/case`) can be used directly without `from __future__ import annotations`.

## Architecture: Clean Layer Separation

### Layers

| Layer | Responsibility | Dependencies |
|-------|---------------|-------------|
| `domain/` | ABCs, events, errors | None |
| `bsl/` | Board Support Layer — PCB-determined hardware (LEDs, Buttons, ADC) | domain |
| `module/` | Pluggable hardware modules — camera (picamera2) | domain |
| `plugin/` | Swappable software components — upload (FTP) | domain |
| `controller/` | Orchestration logic | domain (via injection) |
| `config.py` | Nested Config dataclass, validated from YAML | None |
| `__main__.py` | Wiring + OTCamera main loop | Everything |

### Component Classification

| Category | What lives here | Selection mechanism |
|----------|----------------|---------------------|
| `bsl/` | Soldered, PCB-determined components (LEDs, Buttons, ADC) | `hardware.pcb_version` selects a board profile via `BoardProvider` |
| `module/` | Pluggable hardware modules (camera, future: GNSS, LTE) | Individual provider per component |
| `plugin/` | Swappable software components (upload, future: message broker) | Individual provider per component |

### Directory Structure

```
OTCamera/
├── domain/
│   ├── camera.py              # Camera ABC + CameraClosedError + type literals
│   ├── adc.py                 # ADC ABC + ADCConfig frozen dataclass
│   ├── led.py                 # LED ABC (on, off, blink, pulse)
│   ├── button.py              # Button ABC (on_pressed, on_held, on_released, is_pressed)
│   ├── upload.py              # Upload ABC (upload, is_available)
│   └── events.py              # EventBus + event dataclasses
│
├── bsl/
│   ├── boards/
│   │   ├── board.py           # Board Protocol (structural typing contract)
│   │   └── v2.py              # Board definition: pins, addresses, ratios for PCB v2
│   ├── board_provider.py      # Selects board def by pcb_version, instantiates all BSL components
│   ├── led/
│   │   └── pwm_led.py         # Generic PWM LED (pin injected)
│   ├── button/
│   │   └── gpio_button.py     # Generic GPIO button (pin, pull-up injected)
│   └── adc/
│       └── tla2024.py         # TLA2024 (I2C address, FSR injected)
│
├── module/
│   └── camera/
│       ├── camera_provider.py # CameraProvider.provide(config) → Camera
│       └── picamera2.py       # picamera2 implementation
│
├── plugin/
│   └── upload/
│       ├── upload_provider.py # UploadProvider.provide(config) → Optional[Upload]
│       └── ftp_upload.py      # FTP/FTPS implementation
│
├── controller/
│   ├── camera_controller.py   # Recording orchestration, disk space, preview
│   ├── power_controller.py    # ADC monitoring, power button shutdown, battery events
│   ├── wifi_controller.py     # Wi-Fi toggle via button, delayed off timer
│   ├── schedule_controller.py # Recording schedule, 24/7 mode via hour switch
│   └── upload_controller.py   # Subscribes to RecordingSplit events
│
├── config.py                  # Config dataclass, validated from YAML
├── log.py                     # setup_logging(config), MsTeamsHandler
├── __main__.py                # Wiring + OTCamera main loop
├── html_updater.py            # Status website updater
├── gui/
└── version.py
```

### Deleted

- `hardware/` directory — controllers move to `controller/`, BSL components to `bsl/`
- `plugin/camera/` — picamerax dropped, picamera2 moves to `module/camera/`
- `plugin/adc/` — moves to `bsl/adc/`, selection handled by `BoardProvider`
- `plugin_ftp_server/` — replaced by `plugin/upload/`
- `abstraction/singleton.py` — no longer needed
- `status.py` — eliminated; controllers are queried directly by `__main__.py`. If multiple consumers need aggregated state, a dedicated aggregator may be introduced
- `record.py` — recording mechanics absorbed into `CameraController`, orchestration loop into `OTCamera` class in `__main__.py`
- `helpers/name.py` — absorbed into camera controller
- `helpers/filesystem.py` — absorbed into camera controller
- `helpers/rpi.py` — absorbed into power controller
- `helpers/errors.py` — replaced by domain-level error types
- `helpers/` directory — helpers absorbed into controllers; `helpers/log.py` replaced by `OTCamera/log.py`
- `bsl/boards/v1.py` — only PCB v2 is supported

## Key Decisions

### Config

`Config` is a nested dataclass hierarchy validated on YAML load. `parse_user_config()` reads YAML and returns a `Config` instance. No global singleton — the instance is passed via constructor injection.

### Hardware Abstractions

All hardware behind ABCs in `domain/`. All hardware ABCs declare `close()` for resource cleanup. Functional API per ABC:
- `Camera` — existing ABC. Type literals for exposure/AWB/DRC/meter modes.
- `ADC` — existing ABC + `ADCConfig` frozen dataclass for board-specific parameters (channels, divider ratios).
- `LED` — models individual LED: `on()`, `off()`, `blink(on_time, off_time, n, background)`, `pulse(fade_in_time, fade_out_time, n, background)`. Pattern logic (blink 2x for external power) lives in controllers, not LED implementation.
- `Button` — `on_pressed(callback)`, `on_held(callback)`, `on_released(callback)`, `is_pressed`. Pure hardware semantics — translation to event bus events happens in `__main__.py` wiring.
- `Upload` — `upload(file_path)`, `is_available()`. FTP is first implementation.

### Error Types

Custom error classes live in `domain/` next to the corresponding ABC. Only defined when controllers or main need to react specifically. Otherwise, standard exceptions (`ValueError`, `OSError`) suffice.

| Error | File | Trigger |
|-------|------|---------|
| `CameraClosedError` | `domain/camera.py` | Method called on closed camera |
| `ADCTimeoutError` | `domain/adc.py` | I2C error or conversion timeout |
| `UploadError` | `domain/upload.py` | Upload failed (connection, transfer) |

### Resource Cleanup

`BoardComponents.close()` must be exception-safe: log and continue so one failure does not prevent cleanup of remaining resources.

### Providers

- `BoardProvider` — single entry point for all BSL components. Reads `hardware.pcb_version`, loads board definition, instantiates LEDs/buttons/ADC. Returns a `BoardComponents` bundle (`leds: dict[str, LED]`, `buttons: dict[str, Button]`, `adc: ADC | None`, `adc_config: ADCConfig | None`). If `provide()` fails, it must close any already-created components before propagating the exception.
- `CameraProvider` (in `module/camera/`) — lazy import of picamera2. Returns `Camera` instance.
- `UploadProvider` (in `plugin/upload/`) — returns `Optional[Upload]` based on config. Lazy import of FTP implementation.

### Board Support Layer

Board definitions are frozen dataclasses in `bsl/boards/` — pure data, no logic. A `Board` Protocol enforces the structural typing contract. Only PCB v2 is supported.

BSL implementations are generic — they implement domain ABCs and receive board-specific parameters via constructor injection:
- `PwmLed(pin: int)` — generic PWM LED using gpiozero.PWMLED
- `GpioButton(pin: int, pull_up: bool, hold_time: float)` — generic GPIO button using gpiozero.Button
- `TLA2024(i2c_address: int, fsr: float)` — TLA2024 ADC using smbus2. I2C errors wrapped as `ADCTimeoutError`.

Controllers must tolerate absent hardware. When BSL components are disabled via config, dicts are empty and optional components are `None`. Controllers check before use.

### Event Bus

Queue-based in-process pub/sub. Single instance passed via constructor injection. `emit()` must be thread-safe (gpiozero callbacks call it from background threads). API: `subscribe()`, `emit()`, `process_pending()`, `unsubscribe()`, `clear()`. The latter two are for teardown and test isolation.

**Event types:**
```
RecordingStarted(filename: str)
RecordingStopped()
RecordingSplit(filename: str)
IntervalFinished()                     # reserved for future calendar-based scheduling
BatteryLow()
ExternalPowerConnected()
ExternalPowerDisconnected()
ButtonPressed(name: str)
ButtonHeld(name: str)
ButtonReleased(name: str)
PreviewCaptured(path: str)
WifiOn()
WifiOff()
ShutdownRequested(source: str)  # "battery", "button", "ui", "messagebroker"
```

**Error handling:** Log and continue on callback exceptions. Never crash the caller.

**Threading:** `emit()` enqueues events. `process_pending()` is called once per main loop iteration and dispatches all queued events on the main thread. All `subscribe()` calls must complete before any `emit()` — the wiring order in `__main__.py` guarantees this.

### Recording Pipeline (direct method calls)

The recording loop in `__main__.py` uses direct method calls for everything that affects video recording:
- `schedule_controller.should_record()` — determines if now is recording time.
- `camera_controller.start_recording()` / `stop_recording()` / `split_if_interval_ends()`
- `power_controller.check_power_status()` — direct call, emits events for listeners
- `power_controller.check_pending_shutdown()` — checks if power switch shutdown countdown has elapsed
- `wifi_controller.check_pending_wifi_off()` — checks if Wi-Fi off delay has elapsed

Controllers emit events after actions for non-critical subscribers (UI, upload).

### Buttons

Buttons emit events via the event bus. Both physical buttons and future UI buttons are event sources. Handlers don't care where events come from. Button ABCs provide only hardware callbacks; `__main__.py` wiring translates these to event bus events. Toggle switches have state at boot that precedes callback registration. After wiring, controllers must read the initial switch position via `button.is_pressed` and reconcile their state accordingly.

### Schedule Controller

Owns "should we record" logic. Checks if current hour is within start/end hour range, including overnight windows (e.g., start=22, end=6). Hour switch override (24/7 mode): `ButtonPressed("hour")` enables 24/7, `ButtonReleased("hour")` restores schedule.

### Power Controller

Monitors battery/USB voltage via ADC and handles system shutdown. Power switch behavior: switch OFF starts a countdown (seconds), switch back ON cancels it. If the countdown expires, the system shuts down. At boot: power switch OFF triggers immediate shutdown (no countdown). Emits `BatteryLow`, `ExternalPowerConnected`, `ExternalPowerDisconnected`, `ShutdownRequested` events.

### WiFi Controller

Manages Wi-Fi AP state. WiFi switch ON turns Wi-Fi on immediately. Switch OFF starts a delayed timer (configurable), then turns Wi-Fi off. Switching back ON during the delay cancels it. Emits `WifiOn`, `WifiOff` events.

### Upload

Upload controller subscribes to `RecordingSplit` events. Camera controller emits the event and doesn't know about uploading. Note: uploads currently run synchronously on the main thread — a known limitation to address in a future iteration.

### Logging

All code uses Python standard `logging` via `logging.getLogger(__name__)`. The legacy `helpers/log.py` module is replaced by `OTCamera/log.py` which provides:

- `setup_logging(config)` — configures handlers, formatters, log level, logfile path (`prefix_FRfps_timestamp.log`). Called once from `__main__.py` during wiring.
- `MsTeamsHandler(logging.Handler)` — custom handler that posts non-debug messages to MS Teams webhook (if enabled), with retry counter.
- `FileHandler` — logfile output
- `StreamHandler` — stdout output

### Subprocess Calls

System commands (`sudo shutdown`, `sudo rfkill`) use list-form `subprocess.call(["sudo", "shutdown", "-h", "now"])` instead of `shell=True` for safety.

## Wiring (in `__main__.py`)

```python
# 1. Load config
config = parse_user_config(yaml_path)

# 2. Create event bus
event_bus = EventBus()

# 3. BSL — one call, all board-specific components as bundle
board = BoardProvider.provide(config)

# 4. Module — pluggable hardware, independent of PCB version
camera = CameraProvider.provide(config)

# 5. Plugins — swappable software components
upload = UploadProvider.provide(config)

# 6. Controllers — work against domain ABCs only
camera_controller = CameraController(camera, config, event_bus, board.leds)
power_controller = PowerController(config, event_bus, board.leds, board.adc, board.adc_config)
wifi_controller = WifiController(config, event_bus, board.leds)
schedule_controller = ScheduleController(config, event_bus)
upload_controller = UploadController(event_bus, upload)

# 7. Wire buttons to event bus
for name, button in board.buttons.items():
    button.on_pressed(lambda n=name: event_bus.emit(ButtonPressed(n)))
    button.on_released(lambda n=name: event_bus.emit(ButtonReleased(n)))
    button.on_held(lambda n=name: event_bus.emit(ButtonHeld(n)))

# 8. Boot checks — abort before further init if shutdown is needed
if "power" in board.buttons and not board.buttons["power"].is_pressed:
    # Power switch OFF at boot → immediate shutdown
    power_controller.execute_system_shutdown()
    return

# 9. Reconcile initial switch positions (if buttons present)
if "wifi" in board.buttons:
    wifi_controller.init_from_switch(board.buttons["wifi"].is_pressed)
if "hour" in board.buttons:
    schedule_controller.init_from_switch(board.buttons["hour"].is_pressed)

# 10. HTML updater (controllers queried directly, no separate Status class)
html_updater = StatusWebsiteUpdater(template_path, offline_path, index_path, ...)

# 11. Create video directory (parents=True for nested paths)
Path(config.video.dir).mkdir(parents=True, exist_ok=True)

# 12. Run
otcamera = OTCamera(
    camera_controller, power_controller, wifi_controller,
    schedule_controller, html_updater, event_bus,
)
otcamera.record()
```

### Shutdown Safety

- Register both SIGTERM and SIGINT handlers
- Set `_shutdown = True` as the **first** action in `_execute_shutdown` (prevents re-entrant calls)
- If initialization fails before the main object is constructed, acquired resources must still be released. What happens after cleanup (retry, reboot, shutdown, idle) is out of scope for this refactor

## Entry Points

- `run.py` (repo root) — CLI entry: parses args, loads config. If USB device is present, runs `usb_flash_drive_copy`; otherwise calls `OTCamera.__main__`
- `python -m OTCamera` — package entry via `__main__.py` (recording mode only)
- `usb_flash_drive_copy.py` (repo root) — alternative mode: copies videos to USB flash drive. Uses `BoardProvider` for LEDs/buttons, does not initialize camera or controllers

## Configuration

YAML file (see `user_config.example.yaml`). Board-specific parameters (GPIO pins, I2C addresses, divider ratios) live in board definitions, not in user config.

```yaml
hardware:
  pcb_version: v2       # selects board profile
  use_leds: true         # enable/disable toggles
  use_buttons: true
  use_adc: true

camera:
  fps: 20
  resolution:
    width: 1920
    height: 1080

server_upload:
  enable: true
  scheme: ftp            # selects plugin implementation
  host: example.com
```

ADC thresholds remain in user config (deployment-specific, not board-specific).

## Future Extensibility

### New BSL component (e.g., accelerometer)
1. Add ABC in `domain/`
2. Add implementation in `bsl/`
3. Add fields to board definition (use `Optional` with `None` default for boards that lack it)
4. Extend `BoardComponents` and `BoardProvider`
5. Add controller if needed
6. Wire in `__main__.py`

### New hardware module (e.g., GNSS)
1. Add ABC in `domain/`
2. Add implementation in `module/`
3. Add provider in `module/`
4. Add controller if needed
5. Wire in `__main__.py`

### New software plugin (e.g., message broker)
1. Add ABC in `domain/` if needed
2. Add implementation in `plugin/`
3. Add provider in `plugin/`
4. Add controller if needed
5. Wire in `__main__.py`

### New PCB version
1. Add board definition in `bsl/boards/v3.py` (must satisfy `Board` protocol)
2. Register in `_BOARD_REGISTRY` in `board_provider.py`
3. No changes to BSL implementations, controllers, or domain
