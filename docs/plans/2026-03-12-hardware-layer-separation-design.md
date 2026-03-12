# OTCamera v2 — Hardware Layer Separation Design

**Date:** 2026-03-12
**Amends:** `2026-03-05-v2-architecture-refactor-design.md`
**Branch:** `v2`
**Status:** Draft

## Context

The original v2 architecture design places all hardware implementations in a single `plugin/` directory. This does not reflect the physical reality: some components are soldered to the PCB and fully determined by the board revision, while others are physically swappable or purely software-based.

This amendment introduces a three-layer separation for hardware and external-system integration:

| Layer | What lives here | Selection mechanism |
|-------|----------------|---------------------|
| `bsl/` (Board Support Layer) | Soldered, PCB-determined components | `hardware.pcb_version` selects a board profile |
| `plugin/` | Physically swappable hardware modules | Individual provider per component |
| `adapter/` | Software integrations with external systems | Individual provider per component |

## Classification of Components

### BSL — determined by PCB version

These are soldered onto the board. Selecting a PCB version fully determines their configuration (pins, addresses, chip types).

| Component | Current impl | Board-specific parameters |
|-----------|-------------|--------------------------|
| LEDs | PWM via gpiozero | GPIO pins (power, wifi, rec) |
| Buttons | GPIO via gpiozero | GPIO pins, pull-up/down config |
| ADC | TLA2024 via smbus2 | I2C address, FSR, channel mapping, divider ratios |
| Accelerometer | (future) | I2C/SPI address, axes config |

### Plugin — physically swappable modules

These can be exchanged independently of the PCB version.

| Component | Current impl | Selection |
|-----------|-------------|-----------|
| Camera | picamera2 | `camera.type` in config |
| GNSS/LTE module | (future) | Config-based provider |

### Adapter — software integrations

Pure software, no hardware dependency. Connect the domain to external systems.

| Component | Current impl | Selection |
|-----------|-------------|-----------|
| Upload | FTP/FTPS | `server_upload.scheme` in config |
| Message broker | (future) | Config-based provider |

## Architecture

### Layers (updated)

| Layer | Responsibility | Dependencies |
|-------|---------------|-------------|
| `domain/` | ABCs, events, errors | None |
| `bsl/` | Board-specific hardware implementations + board provider | domain |
| `plugin/` | Swappable hardware module implementations + providers | domain |
| `adapter/` | External system integrations + providers | domain |
| `controller/` | Orchestration logic | domain (via injection) |
| `config.py` | Validated Config dataclass, global `CONFIG` | None |
| `status.py` | Event-driven read model, global `STATUS` | domain (events) |
| `__main__.py` | Wiring + main loop | Everything |

### Directory Structure (updated)

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
├── bsl/
│   ├── boards/
│   │   ├── v1.py              # Board definition: pins, addresses, ratios for PCB v1
│   │   └── v2.py              # Board definition: pins, addresses, ratios for PCB v2
│   ├── board_provider.py      # Selects board def by pcb_version, instantiates all BSL components
│   ├── led/
│   │   └── pwm_led.py         # Generic PWM LED (pin injected)
│   ├── button/
│   │   └── gpio_button.py     # Generic GPIO button (pin, pull-up injected)
│   └── adc/
│       └── tla2024.py         # TLA2024 (I2C address, FSR injected)
│
├── plugin/
│   └── camera/
│       ├── camera_provider.py # Selects camera backend by config
│       └── picamera2.py       # picamera2 implementation
│
├── adapter/
│   └── upload/
│       ├── upload_provider.py # Selects upload backend by config
│       └── ftp_upload.py      # FTP/FTPS implementation
│
├── controller/
│   ├── camera_controller.py   # Recording orchestration
│   ├── power_controller.py    # ADC monitoring, emits battery/power events
│   ├── wifi_controller.py     # Wi-Fi toggle, subscribes to button events
│   ├── schedule_controller.py # Recording schedule
│   └── upload_controller.py   # Subscribes to RecordingSplit events
│
├── config.py                  # Config dataclass, validated, global CONFIG
├── status.py                  # Status read model, subscribes to events
├── __main__.py                # Wiring + OTCamera main loop
├── html_updater.py            # Status website
├── helpers/
│   └── log.py
├── abstraction/
│   └── singleton.py
├── gui/
└── version.py
```

### Deleted (updated, same as original design)

- `hardware/` directory -- controllers move to `controller/`, BSL components to `bsl/`
- `plugin/camera/picamerax.py` -- legacy camera backend dropped
- `plugin_ftp_server/` -- replaced by `adapter/upload/`
- `helpers/name.py` -- absorbed into camera controller
- `helpers/filesystem.py` -- absorbed into camera controller
- `helpers/rpi.py` -- absorbed into power controller

## Board Support Layer Details

### Board Definitions

Each PCB version has a frozen dataclass in `bsl/boards/` containing all board-specific parameters. These are pure data -- no logic, no imports beyond stdlib.

```python
# bsl/boards/v2.py
from dataclasses import dataclass


@dataclass(frozen=True)
class BoardV2:
    """Pin mappings and hardware parameters for PCB v2."""

    # LEDs (GPIO pin numbers)
    led_power_pin: int = 11
    led_wifi_pin: int = 12
    led_rec_pin: int = 13

    # Buttons (GPIO pin numbers + config)
    button_power_pin: int = 21
    button_hour_pin: int = 20
    button_wifi_pin: int = 19
    button_power_pull_up: bool = True

    # ADC (TLA2024)
    adc_i2c_address: int = 0x48
    adc_fsr: float = 4.096
    adc_channel_usb: int = 0
    adc_channel_battery: int = 2
    adc_divider_ratio_usb: float = 2.0
    adc_divider_ratio_battery: float = 1510 / 510
```

### BoardProvider

The `BoardProvider` is the single entry point for all BSL components. It reads `hardware.pcb_version` from the config, loads the corresponding board definition, and instantiates all BSL components with the correct parameters.

```python
# bsl/board_provider.py
from dataclasses import dataclass
from typing import Dict, Optional

from OTCamera.domain.adc import ADC
from OTCamera.domain.button import Button
from OTCamera.domain.led import LED


@dataclass
class BoardComponents:
    """All hardware components provided by the board."""

    leds: Dict[str, LED]
    buttons: Dict[str, Button]
    adc: Optional[ADC]


class BoardProvider:
    """Instantiates all BSL components for the configured PCB version."""

    @staticmethod
    def provide(config) -> BoardComponents:
        board = _load_board_definition(config.pcb_version)

        leds = {}
        if config.use_leds:
            leds = {
                "power": PwmLed(board.led_power_pin),
                "recording": PwmLed(board.led_rec_pin),
                "wifi": PwmLed(board.led_wifi_pin),
            }

        buttons = {}
        if config.use_buttons:
            buttons = {
                "power": GpioButton(board.button_power_pin, board.button_power_pull_up),
                "hour": GpioButton(board.button_hour_pin),
                "wifi": GpioButton(board.button_wifi_pin),
            }

        adc = None
        if config.use_adc:
            adc = TLA2024(board.adc_i2c_address, board.adc_fsr)

        return BoardComponents(leds=leds, buttons=buttons, adc=adc)
```

### BSL Implementations

BSL implementations are generic. They implement domain ABCs and receive all board-specific parameters via constructor injection. There is one implementation per component type (not per PCB version).

- `bsl/led/pwm_led.py` -- generic PWM LED, receives GPIO pin
- `bsl/button/gpio_button.py` -- generic GPIO button, receives GPIO pin + pull config
- `bsl/adc/tla2024.py` -- TLA2024 ADC, receives I2C address + FSR

If a future PCB version uses a different ADC chip, a new implementation is added to `bsl/adc/` and the board definition references it (the `BoardProvider` would need to know which ADC class to instantiate per board).

## Plugin and Adapter Details

### Plugins

Plugins use individual providers with the singleton pattern (unchanged from original design):

- `CameraProvider` -- selects camera backend based on `camera.type` config
- Future: `GnssProvider` -- selects GNSS module

Plugins are independent of the PCB version.

### Adapters

Adapters follow the same provider pattern as plugins:

- `UploadProvider` -- selects upload backend based on config (FTP, SFTP, future: S3)
- Future: `MessageBrokerAdapter` -- bridges internal events to MQTT

Adapters have no hardware dependency.

## Config Changes

Board-specific hardware parameters (GPIO pins, I2C addresses, voltage divider ratios) move out of the YAML user config and into board definitions. The user config simplifies to:

```yaml
# user_config.yaml
hardware:
  pcb_version: v2       # selects board profile
  use_leds: true         # enable/disable toggles remain user-configurable
  use_buttons: true
  use_adc: true

camera:
  type: picamera2        # plugin selection, independent of PCB
  fps: 20
  resolution: [1920, 1080]

server_upload:
  scheme: ftp            # adapter selection
  host: example.com
```

ADC thresholds (`adc_threshold_low_battery`, `adc_threshold_external_power`) remain in the user config since they are deployment-specific, not board-specific.

## Wiring (updated `__main__.py`)

```python
# 1. Load config
CONFIG = parse_user_config(yaml_path)

# 2. Create event bus
EVENT_BUS = EventBus()

# 3. BSL -- one call, all board-specific components as bundle
board = BoardProvider.provide(CONFIG)

# 4. Plugins -- independent of PCB version
camera = CameraProvider.provide(CONFIG)

# 5. Adapters -- software integrations
upload = UploadProvider.provide(CONFIG)

# 6. Controllers -- work against domain ABCs only
camera_controller = CameraController(camera, board.leds, CONFIG)
power_controller = PowerController(board.adc, EVENT_BUS, CONFIG)
wifi_controller = WifiController(board.leds, EVENT_BUS)
schedule_controller = ScheduleController(CONFIG, EVENT_BUS)
upload_controller = UploadController(upload, CONFIG, EVENT_BUS)

# 7. Wire buttons to event bus
for name, button in board.buttons.items():
    button.bind(name, EVENT_BUS)

# 8. Read models
STATUS = Status(EVENT_BUS)
html_updater = StatusWebsiteUpdater(STATUS, CONFIG)

# 9. Run
otcamera = OTCamera(
    camera_controller, power_controller, wifi_controller,
    schedule_controller, html_updater, EVENT_BUS,
)
otcamera.record()
```

## Future Extensibility (updated)

### New BSL component (e.g., accelerometer)

1. Add ABC in `domain/accelerometer.py`
2. Add implementation in `bsl/accelerometer/`
3. Add fields to board definitions in `bsl/boards/`
4. Extend `BoardComponents` and `BoardProvider` to include it
5. Add controller in `controller/` if needed
6. Wire in `__main__.py`

### New swappable hardware module (e.g., GNSS)

1. Add ABC in `domain/gnss.py`
2. Add implementation in `plugin/gnss/`
3. Add provider in `plugin/gnss/gnss_provider.py`
4. Add controller in `controller/` if needed
5. Wire in `__main__.py`

### New software adapter (e.g., message broker)

1. Add ABC in `domain/` if needed
2. Add implementation in `adapter/`
3. Add provider in `adapter/`
4. Wire in `__main__.py`

### New PCB version

1. Add board definition in `bsl/boards/v3.py`
2. Register in `BoardProvider`
3. No changes to BSL implementations, controllers, or domain

## Unchanged from Original Design

The following sections from `2026-03-05-v2-architecture-refactor-design.md` remain valid without modification:

- **Domain ABCs** -- Camera, ADC, LED, Button, Upload interfaces unchanged
- **Event Bus** -- all event types, error handling, synchronous pub/sub
- **Recording Pipeline** -- direct method calls for critical path
- **Controllers** -- same responsibilities and interfaces
- **Config & Status** -- global singletons as dataclasses
- **Buttons** -- emit events via event bus, source-agnostic handlers
- **Schedule Controller** -- owns "should we record" logic
- **Entry Points** -- `run.py` and `python -m OTCamera`
