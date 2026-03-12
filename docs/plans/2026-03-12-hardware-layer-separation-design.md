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
│   ├── camera.py              # Camera ABC + CameraClosedError (exists)
│   ├── adc.py                 # ADC ABC (exists)
│   ├── led.py                 # LED ABC (to be created, designed in original spec)
│   ├── button.py              # Button ABC (to be created, designed in original spec)
│   ├── upload.py              # Upload ABC (to be created, designed in original spec)
│   └── events.py              # EventBus + event dataclasses (to be created)
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

### Deleted (updated from original design)

From original design (unchanged):
- `hardware/` directory -- controllers move to `controller/`, BSL components to `bsl/`
- `plugin/camera/picamerax.py` -- legacy camera backend dropped
- `plugin_ftp_server/` -- replaced by `adapter/upload/`
- `helpers/name.py` -- absorbed into camera controller
- `helpers/filesystem.py` -- absorbed into camera controller
- `helpers/rpi.py` -- absorbed into power controller

Added by this amendment:
- `plugin/adc/` (both `adc_provider.py` and `tla2024.py`) -- moves to `bsl/adc/`, selection handled by `BoardProvider`
- `plugin/led/` and `plugin/button/` -- originally planned in `plugin/` by the original design, now superseded by `bsl/led/` and `bsl/button/`

## Board Support Layer Details

### Board Definitions

Each PCB version has a frozen dataclass in `bsl/boards/` containing all board-specific parameters. These are pure data -- no logic, no imports beyond stdlib.

All board definitions share the same field names. A `Board` protocol enforces this contract at the type level:

```python
# bsl/boards/board.py
from typing import Protocol


class Board(Protocol):
    """Contract for board definitions. All boards must provide these fields."""

    # LEDs
    led_power_pin: int
    led_wifi_pin: int
    led_rec_pin: int

    # Buttons
    button_power_pin: int
    button_hour_pin: int
    button_wifi_pin: int
    button_power_pull_up: bool
    button_hour_pull_up: bool
    button_wifi_pull_up: bool

    # ADC
    adc_i2c_address: int
    adc_fsr: float
    adc_channel_usb: int
    adc_channel_battery: int
    adc_divider_ratio_usb: float
    adc_divider_ratio_battery: float
```

Example board definition:

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

    # Buttons (GPIO pin numbers + pull-up config)
    button_power_pin: int = 21
    button_hour_pin: int = 20
    button_wifi_pin: int = 19
    button_power_pull_up: bool = True
    button_hour_pull_up: bool = True
    button_wifi_pull_up: bool = True

    # ADC (TLA2024)
    adc_i2c_address: int = 0x48
    adc_fsr: float = 4.096
    adc_channel_usb: int = 0
    adc_channel_battery: int = 2
    adc_divider_ratio_usb: float = 2.0
    adc_divider_ratio_battery: float = 1510 / 510
```

**Optional BSL components:** Not all boards may have every component (e.g., accelerometer only on PCB v2+). Board definitions use `Optional` fields with `None` defaults for components that are not present on every board. The `BoardProvider` checks these before instantiation.

### BoardProvider

The `BoardProvider` is the single entry point for all BSL components. It reads `hardware.pcb_version` from the config, loads the corresponding board definition via a registry, and instantiates all BSL components with the correct parameters.

```python
# bsl/board_provider.py
from dataclasses import dataclass
from typing import Dict, Optional

from OTCamera.bsl.adc.tla2024 import TLA2024
from OTCamera.bsl.boards.board import Board
from OTCamera.bsl.boards.v1 import BoardV1
from OTCamera.bsl.boards.v2 import BoardV2
from OTCamera.bsl.button.gpio_button import GpioButton
from OTCamera.bsl.led.pwm_led import PwmLed
from OTCamera.domain.adc import ADC
from OTCamera.domain.button import Button
from OTCamera.domain.led import LED

# Board registry: maps pcb_version string to board definition class
_BOARD_REGISTRY: Dict[str, type] = {
    "v1": BoardV1,
    "v2": BoardV2,
}


@dataclass
class ADCConfig:
    """Board-specific ADC operational parameters for the power controller."""

    channel_usb: int
    channel_battery: int
    divider_ratio_usb: float
    divider_ratio_battery: float


@dataclass
class BoardComponents:
    """All hardware components and parameters provided by the board."""

    leds: Dict[str, LED]
    buttons: Dict[str, Button]
    adc: Optional[ADC]
    adc_config: Optional[ADCConfig]


def _load_board_definition(pcb_version: str) -> Board:
    """Load board definition by PCB version string."""
    if pcb_version not in _BOARD_REGISTRY:
        raise ValueError(
            f"Unknown PCB version: {pcb_version!r}. "
            f"Available: {list(_BOARD_REGISTRY.keys())}"
        )
    return _BOARD_REGISTRY[pcb_version]()


class BoardProvider:
    """Instantiates all BSL components for the configured PCB version."""

    @staticmethod
    def provide(config) -> BoardComponents:
        board = _load_board_definition(config.hardware.pcb_version)

        leds: Dict[str, LED] = {}
        if config.hardware.use_leds:
            leds = {
                "power": PwmLed(board.led_power_pin),
                "recording": PwmLed(board.led_rec_pin),
                "wifi": PwmLed(board.led_wifi_pin),
            }

        buttons: Dict[str, Button] = {}
        if config.hardware.use_buttons:
            buttons = {
                "power": GpioButton(
                    board.button_power_pin, pull_up=board.button_power_pull_up
                ),
                "hour": GpioButton(
                    board.button_hour_pin, pull_up=board.button_hour_pull_up
                ),
                "wifi": GpioButton(
                    board.button_wifi_pin, pull_up=board.button_wifi_pull_up
                ),
            }

        adc: Optional[ADC] = None
        adc_config: Optional[ADCConfig] = None
        if config.hardware.use_adc:
            adc = TLA2024(board.adc_i2c_address, board.adc_fsr)
            adc_config = ADCConfig(
                channel_usb=board.adc_channel_usb,
                channel_battery=board.adc_channel_battery,
                divider_ratio_usb=board.adc_divider_ratio_usb,
                divider_ratio_battery=board.adc_divider_ratio_battery,
            )

        return BoardComponents(
            leds=leds, buttons=buttons, adc=adc, adc_config=adc_config
        )
```

### BSL Implementations

BSL implementations are generic. They implement domain ABCs and receive all board-specific parameters via constructor injection. There is one implementation per component type (not per PCB version).

- `bsl/led/pwm_led.py` -- generic PWM LED, receives GPIO pin. Constructor: `PwmLed(pin: int)`
- `bsl/button/gpio_button.py` -- generic GPIO button, receives GPIO pin + pull config. Constructor: `GpioButton(pin: int, pull_up: bool = True, hold_time: float = 3.0)`
- `bsl/adc/tla2024.py` -- TLA2024 ADC, receives I2C address + FSR. Constructor: `TLA2024(i2c_address: int = 0x48, fsr: float = 4.096)`

If a future PCB version uses a different ADC chip, a new implementation is added to `bsl/adc/` and the board definition references it (the `BoardProvider` would need to know which ADC class to instantiate per board).

### Button Event Binding

The `Button` domain ABC includes a `bind(name, event_bus)` method. This is part of the abstract interface — all button implementations must support it. The method registers the button's press/hold callbacks to emit `ButtonPressed(name)` and `ButtonHeld(name)` events on the given event bus.

```python
# domain/button.py (relevant part)
from abc import ABC, abstractmethod


class Button(ABC):
    """Abstract button interface."""

    @abstractmethod
    def bind(self, name: str, event_bus: "EventBus") -> None:
        """Register this button to emit named events on the event bus."""
        ...
```

This means `bind()` is called during wiring, not during construction. The `GpioButton` implementation sets up gpiozero callbacks that emit `ButtonPressed(name)` and `ButtonHeld(name)` events.

### Controller Contracts

Controllers must tolerate empty LED/button dicts. When `config.hardware.use_leds` is `false`, `board.leds` is `{}`. Controllers that use LEDs (e.g., `CameraController`, `WifiController`) check for key presence before calling LED methods. This is a contract: controllers never assume a specific LED exists.

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
  resolution:
    width: 1920
    height: 1080

server_upload:
  scheme: ftp            # adapter selection
  host: example.com
```

ADC thresholds (`adc_threshold_low_battery`, `adc_threshold_external_power`) remain in the user config since they are deployment-specific, not board-specific.

Config access in pseudocode uses nested attributes matching the YAML structure (e.g., `config.hardware.pcb_version`, `config.hardware.use_leds`). The `Config` dataclass (designed in the original spec) validates and provides these as typed fields.

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
power_controller = PowerController(board.adc, board.adc_config, EVENT_BUS, CONFIG)
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

Note: The original design's wiring had an undefined `upload_plugin` variable. This amendment fixes that by explicitly showing `upload = UploadProvider.provide(CONFIG)` in step 5.

## Future Extensibility (updated)

### New BSL component (e.g., accelerometer)

1. Add ABC in `domain/accelerometer.py`
2. Add implementation in `bsl/accelerometer/`
3. Add fields to board definitions in `bsl/boards/` (use `Optional` fields with `None` default for boards that lack the component)
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

1. Add board definition in `bsl/boards/v3.py` (must satisfy the `Board` protocol)
2. Register in `_BOARD_REGISTRY` in `board_provider.py`
3. No changes to BSL implementations, controllers, or domain

## Unchanged from Original Design

The following **design decisions** from `2026-03-05-v2-architecture-refactor-design.md` carry forward without modification. Note: some of these (LED, Button, Upload ABCs; EventBus) are planned work from the original design that has not yet been implemented in code.

- **Domain ABCs** -- Camera, ADC, LED, Button, Upload interface designs unchanged
- **Event Bus** -- all event types, error handling, synchronous pub/sub
- **Recording Pipeline** -- direct method calls for critical path
- **Controllers** -- same responsibilities and interfaces
- **Config & Status** -- global singletons as dataclasses
- **Buttons** -- emit events via event bus, source-agnostic handlers
- **Schedule Controller** -- owns "should we record" logic
- **Entry Points** -- `run.py` and `python -m OTCamera`
