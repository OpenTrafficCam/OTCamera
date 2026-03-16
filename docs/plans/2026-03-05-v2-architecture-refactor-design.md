# OTCamera v2 Architecture Refactor — Design

**Date:** 2026-03-05
**Branch:** new branch from `v2` (e.g., `v2-refactor`)
**Status:** Approved
**Amended by:** `2026-03-12-hardware-layer-separation-design.md` (splits `plugin/` into `bsl/`, `plugin/`, `adapter/`)

## Context

OTCamera v2 targets new hardware: RPi Zero W2, RPi Camera Module v3, new PCB, Raspi OS Trixie. The codebase needs a clean architecture that allows swapping hardware components (camera, ADC, LEDs, buttons, GPS, LTE, accelerometer) without refactoring core logic. Upcoming features include a web UI, message broker integration, GPS, LTE, and accelerometer support.

## Architecture: Clean Layer Separation

### Layers

> **Superseded:** The layers below are from the original design. The amendment splits
> `plugin/` into `bsl/`, `plugin/`, and `adapter/`. See the amendment for current layers.

| Layer | Responsibility | Dependencies |
|-------|---------------|-------------|
| `domain/` | ABCs, events, errors | None |
| `plugin/` | Hardware implementations + providers | domain |
| `controller/` | Orchestration logic | domain, plugin (via injection) |
| `config.py` | Validated Config dataclass, global `CONFIG` | None |
| ~~`status.py`~~ | ~~Event-driven read model, global `STATUS`~~ | ~~domain (events)~~ |
| `__main__.py` | Wiring + main loop | Everything |

### Directory Structure

> **Superseded:** The directory structure below is from the original design. The amendment
> (`2026-03-12-hardware-layer-separation-design.md`) replaces `plugin/adc/`, `plugin/led/`,
> and `plugin/button/` with `bsl/` and adds `adapter/`. See the amendment for the current
> directory structure.

```
OTCamera/
├── domain/
│   ├── camera.py              # Camera ABC + CameraClosedError
│   ├── adc.py                 # ADC ABC
│   ├── led.py                 # LED ABC (on, off, blink, pulse)
│   ├── button.py              # Button ABC
│   ├── upload.py              # Upload ABC
│   └── events.py              # EventBus + event dataclasses
│
├── plugin/
│   ├── camera/
│   │   ├── camera_provider.py
│   │   └── picamera2.py
│   ├── adc/
│   │   ├── adc_provider.py
│   │   └── tla2024.py
│   ├── led/
│   │   ├── led_provider.py
│   │   └── pwm_led.py
│   ├── button/
│   │   ├── button_provider.py
│   │   └── gpio_button.py
│   └── upload/
│       ├── upload_provider.py
│       └── ftp_upload.py
│
├── controller/
│   ├── camera_controller.py   # Recording orchestration
│   ├── power_controller.py    # ADC monitoring, emits battery/power events
│   ├── wifi_controller.py     # Wi-Fi toggle, subscribes to button events
│   ├── schedule_controller.py # Recording schedule (future: calendar)
│   └── upload_controller.py   # Subscribes to RecordingSplit events
│
├── config.py                  # Config dataclass, validated, global CONFIG
├── status.py                  # Status read model, subscribes to events
├── __main__.py                # Wiring + OTCamera main loop
├── html_updater.py            # Status website
├── helpers/
│   └── log.py                 # Logging setup (only remaining helper)
├── abstraction/
│   └── singleton.py
├── gui/
└── version.py
```

### Deleted

- `hardware/` directory — controllers move to `controller/`, hardware to `plugin/`
- `plugin/camera/picamerax.py` — legacy camera backend dropped
- `plugin_ftp_server/` — replaced by `plugin/upload/`
- `helpers/name.py` — absorbed into camera controller
- `helpers/filesystem.py` — absorbed into camera controller
- `helpers/rpi.py` — absorbed into power controller

## Key Decisions

### Config & Status (global singletons as classes)

> **Superseded (Status):** The implementation plan eliminates `status.py`. Controllers are
> queried directly by the `OTCamera` class in `__main__.py`. Config remains as designed.

- `Config`: dataclass with typed fields, validated on YAML load. Accessed as `from OTCamera.config import CONFIG`.
- ~~`Status`: read model that subscribes to events and accumulates current state.~~
- No full dependency injection for config — global singleton is pragmatic for this scale.

### Hardware Abstractions

All hardware behind ABCs in `domain/`:
- `Camera` — existing, `CameraClosedError` merged in
- `ADC` — existing, unchanged
- `LED` — new. Models individual LED: `on()`, `off()`, `blink(n, speed)`, `pulse()`. Provider returns dict of named LEDs (`{"power": led, "recording": led, "wifi": led}`). Pattern logic (blink 2x for external power) lives in controllers, not LED plugin.
- `Button` — new. Hardware detects press/hold, emits events on the event bus.
- `Upload` — new. `upload(file_path)`, `is_available()`. FTP is first implementation.

### Providers

All hardware uses providers (singleton pattern) for runtime selection:
- `CameraProvider` — selects camera backend (currently only picamera2, future extensibility)
- `ADCProvider` — returns ADC or None based on config
- `LEDProvider` — selects by PCB version, returns named LED dict
- `ButtonProvider` — selects by PCB version, wires events
- `UploadProvider` — selects upload backend

### Event Bus

Synchronous in-process pub/sub. Single global instance.

**Event types:**
```
RecordingStarted(filename: str)
RecordingStopped()
RecordingSplit(filename: str)
IntervalFinished()
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

**Error handling:** Log and continue on callback exceptions. Never crash. The event bus does not handle system-critical operations.

### Recording Pipeline (direct method calls)

The recording loop in `__main__.py` uses direct method calls for everything that affects video recording:
- `schedule_controller.should_record()` — determines if now is recording time
- `camera_controller.start_recording()` / `stop_recording()` / `split_if_interval_ends()`
- `power_controller.check_power_status()` — direct call, but emits events for listeners

Controllers emit events after actions for non-critical subscribers (Status, UI, LEDs, upload).

### Buttons

Buttons emit events via the event bus. Both physical buttons and future UI buttons are event sources. Handlers don't care where events come from.

### Schedule Controller

Owns "should we record" logic. Currently: check if current hour is within start/end hour range. Future: calendar-based recording windows. Hour switch override (24/7 mode) handled here: `ButtonPressed("hour")` enables 24/7 mode (switch ON), `ButtonReleased("hour")` restores scheduled hours (switch OFF).

### Upload

Upload controller subscribes to `RecordingSplit` events. Camera controller emits the event and doesn't know about uploading. Clean separation.

## Wiring (in `__main__.py`)

> **Superseded:** The wiring below uses the original `plugin/` layout. See the amendment
> for updated wiring with `BoardProvider`, `CameraProvider`, and `UploadProvider`.

```python
# 1. Load config
CONFIG = parse_user_config(yaml_path)

# 2. Create event bus
EVENT_BUS = EventBus()

# 3. Create plugins via providers
camera = CameraProvider.provide(CONFIG)
adc = ADCProvider.provide(CONFIG)
leds = LEDProvider.provide(CONFIG)
buttons = ButtonProvider.provide(CONFIG, EVENT_BUS)

# 4. Create controllers
camera_controller = CameraController(camera, leds, CONFIG)
power_controller = PowerController(adc, EVENT_BUS)
wifi_controller = WifiController(leds, EVENT_BUS)
schedule_controller = ScheduleController(CONFIG, EVENT_BUS)
upload_controller = UploadController(upload_plugin, CONFIG)

# 5. Create read models
STATUS = Status(EVENT_BUS)
html_updater = StatusWebsiteUpdater(STATUS, CONFIG)

# 6. Run
otcamera = OTCamera(
    camera_controller, power_controller, wifi_controller,
    schedule_controller, html_updater, EVENT_BUS,
)
otcamera.record()
```

## Entry Points

- `run.py` (repo root) — CLI entry: parses args, loads config, calls `OTCamera.__main__`
- `python -m OTCamera` — package entry via `__main__.py`

## Future Extensibility

New hardware component (GPS, LTE, accelerometer):
1. Add ABC in `domain/`
2. Add implementation in `plugin/`
3. Add provider in `plugin/`
4. Add controller in `controller/` if needed
5. Wire in `__main__.py`
6. Emit/subscribe events as appropriate

No existing code changes required. The pattern is established and mechanical to follow.

External message broker (future): becomes another event subscriber/publisher that bridges internal events to MQTT or similar.
