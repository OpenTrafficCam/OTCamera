# v2 Architecture Refactor — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor OTCamera into clean layers (domain / bsl / plugin / adapter / controller) with event bus, hardware ABCs, board support layer, and provider pattern for swappable components.

**Architecture:** Domain ABCs define contracts. BSL (Board Support Layer) implements board-specific hardware (LEDs, buttons, ADC) selected by PCB version via a single BoardProvider. Plugins implement swappable hardware modules (camera). Adapters handle external system integrations (upload). Controllers orchestrate logic against domain ABCs only. EventBus connects non-critical communication. Config/Status are global singleton classes.

**Tech Stack:** Python 3.9+, gpiozero, picamera2, smbus2, psutil, pyyaml, beautifulsoup4, pytest

**Design docs:**
- `docs/plans/2026-03-05-v2-architecture-refactor-design.md`
- `docs/plans/2026-03-12-hardware-layer-separation-design.md` (amends the above)

---

### Task 1: Create branch and project scaffolding

**Files:**
- Create: `OTCamera/controller/__init__.py`
- Create: `OTCamera/bsl/__init__.py`
- Create: `OTCamera/bsl/boards/__init__.py`
- Create: `OTCamera/bsl/led/__init__.py`
- Create: `OTCamera/bsl/button/__init__.py`
- Create: `OTCamera/bsl/adc/__init__.py`
- Create: `OTCamera/adapter/__init__.py`
- Create: `OTCamera/adapter/upload/__init__.py`

- [ ] **Step 1: Create branch from v2**

```bash
git checkout v2
git checkout -b v2-refactor
```

- [ ] **Step 2: Create empty package directories**

```bash
mkdir -p OTCamera/controller
touch OTCamera/controller/__init__.py
mkdir -p OTCamera/bsl/boards
touch OTCamera/bsl/__init__.py
touch OTCamera/bsl/boards/__init__.py
mkdir -p OTCamera/bsl/led
touch OTCamera/bsl/led/__init__.py
mkdir -p OTCamera/bsl/button
touch OTCamera/bsl/button/__init__.py
mkdir -p OTCamera/bsl/adc
touch OTCamera/bsl/adc/__init__.py
mkdir -p OTCamera/adapter/upload
touch OTCamera/adapter/__init__.py
touch OTCamera/adapter/upload/__init__.py
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: scaffold new package directories for refactor"
```

---

### Task 2: Event bus (domain/events.py)

**Files:**
- Create: `OTCamera/domain/events.py`
- Create: `tests/domain/test_events.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/test_events.py
import pytest

from OTCamera.domain.events import (
    BatteryLow,
    ButtonHeld,
    ButtonPressed,
    ButtonReleased,
    EventBus,
    ExternalPowerConnected,
    ExternalPowerDisconnected,
    IntervalFinished,
    PreviewCaptured,
    RecordingSplit,
    RecordingStarted,
    RecordingStopped,
    ShutdownRequested,
    WifiOff,
    WifiOn,
)


class TestEventBus:
    def test_subscribe_and_emit(self) -> None:
        bus = EventBus()
        received: list[RecordingStarted] = []
        bus.subscribe(RecordingStarted, received.append)
        event = RecordingStarted(filename="/tmp/video.h264")
        bus.emit(event)
        assert received == [event]

    def test_multiple_subscribers(self) -> None:
        bus = EventBus()
        results_a: list[BatteryLow] = []
        results_b: list[BatteryLow] = []
        bus.subscribe(BatteryLow, results_a.append)
        bus.subscribe(BatteryLow, results_b.append)
        bus.emit(BatteryLow())
        assert len(results_a) == 1
        assert len(results_b) == 1

    def test_no_cross_talk(self) -> None:
        bus = EventBus()
        received: list[WifiOn] = []
        bus.subscribe(WifiOn, received.append)
        bus.emit(WifiOff())
        assert received == []

    def test_callback_exception_does_not_propagate(self) -> None:
        bus = EventBus()
        results: list[BatteryLow] = []

        def bad_callback(event: BatteryLow) -> None:
            raise RuntimeError("boom")

        bus.subscribe(BatteryLow, bad_callback)
        bus.subscribe(BatteryLow, results.append)
        bus.emit(BatteryLow())
        assert len(results) == 1

    def test_event_dataclass_fields(self) -> None:
        e = RecordingStarted(filename="vid.h264")
        assert e.filename == "vid.h264"

        e2 = RecordingSplit(filename="vid2.h264")
        assert e2.filename == "vid2.h264"

        e3 = PreviewCaptured(path="/tmp/preview.jpg")
        assert e3.path == "/tmp/preview.jpg"

        e4 = ShutdownRequested(source="battery")
        assert e4.source == "battery"

        e5 = ButtonPressed(name="power")
        assert e5.name == "power"

        e6 = ButtonHeld(name="wifi")
        assert e6.name == "wifi"

        e7 = ButtonReleased(name="hour")
        assert e7.name == "hour"

    def test_events_without_fields(self) -> None:
        for cls in [
            RecordingStopped,
            IntervalFinished,
            BatteryLow,
            ExternalPowerConnected,
            ExternalPowerDisconnected,
            WifiOn,
            WifiOff,
        ]:
            event = cls()
            assert event is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_events.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the event bus**

```python
# OTCamera/domain/events.py
"""Event bus and event types for OTCamera.

Synchronous in-process pub/sub. Callbacks are invoked in registration order.
Exceptions in callbacks are logged and swallowed — never crash the caller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Type

logger = logging.getLogger(__name__)


# --- Event types ---


@dataclass(frozen=True)
class RecordingStarted:
    filename: str


@dataclass(frozen=True)
class RecordingStopped:
    pass


@dataclass(frozen=True)
class RecordingSplit:
    filename: str


@dataclass(frozen=True)
class IntervalFinished:
    """Reserved for future use (e.g., calendar-based scheduling)."""
    pass


@dataclass(frozen=True)
class BatteryLow:
    pass


@dataclass(frozen=True)
class ExternalPowerConnected:
    pass


@dataclass(frozen=True)
class ExternalPowerDisconnected:
    pass


@dataclass(frozen=True)
class ButtonPressed:
    name: str


@dataclass(frozen=True)
class ButtonHeld:
    name: str


@dataclass(frozen=True)
class ButtonReleased:
    name: str


@dataclass(frozen=True)
class PreviewCaptured:
    path: str


@dataclass(frozen=True)
class WifiOn:
    pass


@dataclass(frozen=True)
class WifiOff:
    pass


@dataclass(frozen=True)
class ShutdownRequested:
    source: str


# --- Event bus ---


class EventBus:
    """Synchronous in-process event bus.

    Subscribe callbacks to event types. When an event is emitted, all
    registered callbacks for that type are called in order. Exceptions
    in callbacks are logged and swallowed.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[Type[Any], List[Callable[[Any], None]]] = {}

    def subscribe(
        self, event_type: Type[Any], callback: Callable[[Any], None]
    ) -> None:
        """Register a callback for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def emit(self, event: Any) -> None:
        """Emit an event to all subscribers. Never raises."""
        for callback in self._subscribers.get(type(event), []):
            try:
                callback(event)
            except Exception:
                logger.exception(
                    "Event callback %s failed for %s", callback, type(event).__name__
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_events.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/domain/events.py tests/domain/test_events.py
git commit -m "feat: add event bus with event types"
```

---

### Task 3: Merge CameraClosedError into camera.py

**Files:**
- Modify: `OTCamera/domain/camera.py` (add error class)
- Delete: `OTCamera/domain/camera_errors.py`
- Modify: `OTCamera/hardware/camera_controller.py` (update import)

- [ ] **Step 1: Add CameraClosedError to camera.py**

Add at line 1 of `OTCamera/domain/camera.py`, before the Camera class:

```python
class CameraClosedError(Exception):
    pass
```

- [ ] **Step 2: Update import in camera_controller.py**

Change:
```python
from OTCamera.domain.camera_errors import CameraClosedError
```
To:
```python
from OTCamera.domain.camera import CameraClosedError
```

- [ ] **Step 3: Search for any other imports of camera_errors and update them**

Run: `grep -r "camera_errors" OTCamera/ tests/`

Update all found imports to use `from OTCamera.domain.camera import CameraClosedError`.

- [ ] **Step 4: Delete camera_errors.py**

```bash
rm OTCamera/domain/camera_errors.py
```

- [ ] **Step 5: Run existing tests**

Run: `pytest -v`
Expected: all existing tests pass

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: merge CameraClosedError into domain/camera.py"
```

---

### Task 4: LED domain ABC

**Files:**
- Create: `OTCamera/domain/led.py`
- Create: `tests/domain/test_led.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_led.py
import pytest

from OTCamera.domain.led import LED


class FakeLED(LED):
    def __init__(self) -> None:
        self._state = "off"

    def on(self) -> None:
        self._state = "on"

    def off(self) -> None:
        self._state = "off"

    def blink(
        self,
        on_time: float = 0.1,
        off_time: float = 0.1,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        self._state = "blink"

    def pulse(
        self,
        fade_in_time: float = 0.25,
        fade_out_time: float = 0.25,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        self._state = "pulse"


class TestLEDABC:
    def test_can_instantiate_concrete_led(self) -> None:
        led = FakeLED()
        assert led is not None

    def test_on_off(self) -> None:
        led = FakeLED()
        led.on()
        assert led._state == "on"
        led.off()
        assert led._state == "off"

    def test_blink(self) -> None:
        led = FakeLED()
        led.blink(on_time=0.1, off_time=0.1, n=2)
        assert led._state == "blink"

    def test_pulse(self) -> None:
        led = FakeLED()
        led.pulse(fade_in_time=0.5, fade_out_time=0.5, n=4)
        assert led._state == "pulse"

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            LED()  # type: ignore[abstract]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_led.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the LED ABC**

```python
# OTCamera/domain/led.py
"""Abstract LED interface.

Models a single LED with on/off/blink/pulse capabilities.
Pattern logic (e.g., blink 2x for external power) lives in controllers,
not in the LED implementation.
"""

from abc import ABC, abstractmethod


class LED(ABC):

    @abstractmethod
    def on(self) -> None:
        """Turn the LED on."""
        raise NotImplementedError

    @abstractmethod
    def off(self) -> None:
        """Turn the LED off."""
        raise NotImplementedError

    @abstractmethod
    def blink(
        self,
        on_time: float = 0.1,
        off_time: float = 0.1,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        """Blink the LED.

        Args:
            on_time: Seconds the LED stays on per blink.
            off_time: Seconds the LED stays off per blink.
            n: Number of blinks. None for infinite.
            background: Run in background thread if True.
        """
        raise NotImplementedError

    @abstractmethod
    def pulse(
        self,
        fade_in_time: float = 0.25,
        fade_out_time: float = 0.25,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        """Pulse (fade in/out) the LED.

        Args:
            fade_in_time: Seconds to fade in.
            fade_out_time: Seconds to fade out.
            n: Number of pulses. None for infinite.
            background: Run in background thread if True.
        """
        raise NotImplementedError
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_led.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/domain/led.py tests/domain/test_led.py
git commit -m "feat: add LED abstract interface"
```

---

### Task 5: Button domain ABC

**Files:**
- Create: `OTCamera/domain/button.py`
- Create: `tests/domain/test_button.py`

The Button ABC uses a `bind(name, event_bus)` method instead of constructor injection.
Construction creates the hardware object; `bind()` connects it to the event bus — called
during wiring in `__main__.py`. This separation allows the BoardProvider to create buttons
without knowing their names or the event bus.

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_button.py
import pytest

from OTCamera.domain.button import Button
from OTCamera.domain.events import ButtonHeld, ButtonPressed, ButtonReleased, EventBus


class FakeButton(Button):
    def __init__(self) -> None:
        self._pressed = False
        self._name: str | None = None
        self._event_bus: EventBus | None = None

    def bind(self, name: str, event_bus: EventBus) -> None:
        self._name = name
        self._event_bus = event_bus

    @property
    def is_pressed(self) -> bool:
        return self._pressed

    def simulate_press(self) -> None:
        self._pressed = True
        if self._event_bus and self._name:
            self._event_bus.emit(ButtonPressed(name=self._name))

    def simulate_hold(self) -> None:
        if self._event_bus and self._name:
            self._event_bus.emit(ButtonHeld(name=self._name))

    def simulate_release(self) -> None:
        self._pressed = False
        if self._event_bus and self._name:
            self._event_bus.emit(ButtonReleased(name=self._name))


class TestButtonABC:
    def test_bind_and_press_emits_event(self) -> None:
        bus = EventBus()
        received: list[ButtonPressed] = []
        bus.subscribe(ButtonPressed, received.append)
        btn = FakeButton()
        btn.bind("power", bus)
        btn.simulate_press()
        assert len(received) == 1
        assert received[0].name == "power"

    def test_bind_and_hold_emits_event(self) -> None:
        bus = EventBus()
        received: list[ButtonHeld] = []
        bus.subscribe(ButtonHeld, received.append)
        btn = FakeButton()
        btn.bind("wifi", bus)
        btn.simulate_hold()
        assert len(received) == 1
        assert received[0].name == "wifi"

    def test_bind_and_release_emits_event(self) -> None:
        bus = EventBus()
        received: list[ButtonReleased] = []
        bus.subscribe(ButtonReleased, received.append)
        btn = FakeButton()
        btn.bind("hour", bus)
        btn.simulate_release()
        assert len(received) == 1
        assert received[0].name == "hour"

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            Button()  # type: ignore[abstract]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_button.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the Button ABC**

```python
# OTCamera/domain/button.py
"""Abstract Button interface.

Buttons detect physical presses/holds and emit events on the event bus.
Construction creates the hardware object. bind() connects it to the event
bus with a name — called during wiring in __main__.py.
"""

from abc import ABC, abstractmethod

from OTCamera.domain.events import EventBus


class Button(ABC):
    """Abstract button that emits events on press/hold after binding."""

    @abstractmethod
    def bind(self, name: str, event_bus: EventBus) -> None:
        """Register this button to emit named events on the event bus.

        Args:
            name: Identifier for this button (e.g., "power", "wifi", "hour").
            event_bus: The event bus to emit button events on.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def is_pressed(self) -> bool:
        """Whether the button is currently pressed."""
        raise NotImplementedError
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_button.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/domain/button.py tests/domain/test_button.py
git commit -m "feat: add Button abstract interface with bind pattern"
```

---

### Task 6: Upload domain ABC

**Files:**
- Create: `OTCamera/domain/upload.py`
- Create: `tests/domain/test_upload.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_upload.py
import pytest

from OTCamera.domain.upload import Upload


class FakeUpload(Upload):
    def __init__(self, available: bool = True) -> None:
        self._available = available
        self.uploaded_files: list[str] = []

    def upload(self, file_path: str) -> None:
        self.uploaded_files.append(file_path)

    def is_available(self) -> bool:
        return self._available


class TestUploadABC:
    def test_upload(self) -> None:
        uploader = FakeUpload()
        uploader.upload("/tmp/video.h264")
        assert uploader.uploaded_files == ["/tmp/video.h264"]

    def test_is_available(self) -> None:
        assert FakeUpload(available=True).is_available()
        assert not FakeUpload(available=False).is_available()

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            Upload()  # type: ignore[abstract]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_upload.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the Upload ABC**

```python
# OTCamera/domain/upload.py
"""Abstract upload interface.

Defines the contract for uploading recorded video files to external storage.
"""

from abc import ABC, abstractmethod


class Upload(ABC):

    @abstractmethod
    def upload(self, file_path: str) -> None:
        """Upload a file to external storage.

        Args:
            file_path: Absolute path to the file to upload.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the upload destination is reachable.

        Returns:
            True if upload is possible, False otherwise.
        """
        raise NotImplementedError
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_upload.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/domain/upload.py tests/domain/test_upload.py
git commit -m "feat: add Upload abstract interface"
```

---

### Task 7: ADCConfig domain type

**Files:**
- Modify: `OTCamera/domain/adc.py` (add ADCConfig dataclass)
- Create: `tests/domain/test_adc.py`

Board-specific ADC operational parameters (channels, divider ratios) are defined in board
definitions but used by controllers. To keep controllers independent of the BSL layer,
`ADCConfig` lives in the domain alongside the `ADC` ABC.

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_adc.py
import pytest

from OTCamera.domain.adc import ADCConfig


class TestADCConfig:
    def test_fields(self) -> None:
        cfg = ADCConfig(
            channel_usb=0,
            channel_battery=2,
            divider_ratio_usb=2.0,
            divider_ratio_battery=2.96,
        )
        assert cfg.channel_usb == 0
        assert cfg.channel_battery == 2
        assert cfg.divider_ratio_usb == pytest.approx(2.0)
        assert cfg.divider_ratio_battery == pytest.approx(2.96)

    def test_frozen(self) -> None:
        cfg = ADCConfig(
            channel_usb=0,
            channel_battery=2,
            divider_ratio_usb=2.0,
            divider_ratio_battery=2.96,
        )
        with pytest.raises(AttributeError):
            cfg.channel_usb = 1  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_adc.py -v`
Expected: FAIL (cannot import ADCConfig)

- [ ] **Step 3: Add ADCConfig to domain/adc.py**

Add at the end of `OTCamera/domain/adc.py`, after the ADC ABC:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ADCConfig:
    """Board-specific ADC operational parameters.

    Provided by the BoardProvider based on the PCB version.
    Used by PowerController to read correct channels and apply
    voltage divider ratios.
    """

    channel_usb: int
    channel_battery: int
    divider_ratio_usb: float
    divider_ratio_battery: float
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_adc.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/domain/adc.py tests/domain/test_adc.py
git commit -m "feat: add ADCConfig domain type for board-specific ADC parameters"
```

---

### Task 8: Config dataclass

**Files:**
- Rewrite: `OTCamera/config.py`
- Create: `tests/test_config.py`

Key changes from original design: Hardware pin mappings and ADC hardware parameters move
out of user config into board definitions (BSL). The `hardware:` section gains `use_leds`,
`use_buttons`, `use_adc` enable toggles. The `adc:` section keeps only deployment-specific
thresholds.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import textwrap
from pathlib import Path

import pytest

from OTCamera.config import (
    AdcConfig,
    CameraConfig,
    Config,
    HardwareConfig,
    PreviewConfig,
    RecordingConfig,
    ServerUploadConfig,
    VideoConfig,
    WifiConfig,
    parse_user_config,
)


@pytest.fixture
def minimal_yaml(tmp_path: Path) -> Path:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        debug_mode:
          enable: true
        recording:
          start_hour: 7
          end_hour: 20
          interval_length: 10
          num_intervals: 0
          min_free_space: 2
        camera:
          fps: 15
          resolution:
            width: 1920
            height: 1080
          exposure_mode: auto
          drc_strength: off
          rotation: 0
          awb_mode: auto
          meter_mode: average
        preview:
          path: ~/OTCamera/webfiles/preview.jpg
          format: jpeg
          interval: 5
          send_to_external: false
          url: http://localhost:5000
        video:
          dir: ~/videos/
          format: h264
          resolution:
            width: 640
            height: 480
          encoder:
            profile: high
            level: "4"
            bitrate: 600000
            quality: 30
        wifi:
          delay: 900
        hardware:
          pcb_version: v2
          use_leds: true
          use_buttons: true
          use_adc: true
        msteams:
          enable: false
          url: ""
        adc:
          threshold_external_power: 2.5
          threshold_low_battery: 3.3
        """)
    )
    return config_file


class TestParseUserConfig:
    def test_parse_minimal(self, minimal_yaml: Path) -> None:
        config = parse_user_config(str(minimal_yaml))
        assert config.debug_mode_on is True
        assert config.recording.start_hour == 7
        assert config.recording.end_hour == 20
        assert config.camera.fps == 15
        assert config.camera.resolution == (1920, 1080)
        assert config.hardware.pcb_version == "v2"
        assert config.hardware.use_leds is True
        assert config.hardware.use_buttons is True
        assert config.hardware.use_adc is True
        assert config.adc.threshold_low_battery == 3.3

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        config = parse_user_config(str(tmp_path / "nonexistent.yaml"))
        assert config.camera.fps == 20  # default
        assert config.debug_mode_on is False  # default

    def test_resolution_tuple(self, minimal_yaml: Path) -> None:
        config = parse_user_config(str(minimal_yaml))
        assert config.camera.resolution == (1920, 1080)
        assert config.video.resolution == (640, 480)


class TestConfigDefaults:
    def test_default_config_has_sensible_values(self) -> None:
        config = Config()
        assert config.camera.fps == 20
        assert config.recording.start_hour == 6
        assert config.recording.end_hour == 22
        assert config.hardware.pcb_version == "v1"
        assert config.hardware.use_leds is False
        assert config.hardware.use_buttons is False
        assert config.hardware.use_adc is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (imports not found)

- [ ] **Step 3: Rewrite config.py as dataclass**

```python
# OTCamera/config.py
"""OTCamera configuration.

Config is a dataclass loaded from YAML. A global CONFIG instance is
available after calling parse_user_config().
"""

import logging
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

try:
    from yaml import CSafeLoader as SafeLoader  # type: ignore
except ImportError:
    from yaml import SafeLoader  # type: ignore

import yaml

logger = logging.getLogger(__name__)


@dataclass
class RecordingConfig:
    start_hour: int = 6
    end_hour: int = 22
    interval_length: int = 15
    num_intervals: int = 0
    min_free_space: int = 1


@dataclass
class CameraConfig:
    type: str = "picamera2"
    fps: int = 20
    resolution: tuple[int, int] = (2304, 1296)
    exposure_mode: str = "nightpreview"
    drc_strength: str = "high"
    rotation: int = 180
    awb_mode: str = "greyworld"
    meter_mode: str = "average"


@dataclass
class PreviewConfig:
    path: str = "~/OTCamera/webfiles/preview.jpg"
    format: str = "jpeg"
    interval: int = 5
    send_to_external: bool = False
    url: str = "http://localhost:5000/projects/0/sites/1/cameras/2/current_frame"


@dataclass
class ServerUploadConfig:
    upload: bool = False
    scheme: str = "ftp"
    host: str = "localhost"
    port: int = 21
    user: str = "user"
    password: str = "password"
    server_source: str = "/"


@dataclass
class VideoConfig:
    dir: str = "~/videos/"
    format: Literal["h264"] = "h264"
    resolution: tuple[int, int] = (800, 600)
    h264_profile: Literal["baseline", "main", "high", "constrained"] = "high"
    h264_level: str = "4"
    h264_bitrate: int = 600000
    h264_quality: int = 30


@dataclass
class WifiConfig:
    delay: int = 900


@dataclass
class HardwareConfig:
    pcb_version: Literal["v1", "v2"] = "v1"
    use_leds: bool = False
    use_buttons: bool = False
    use_adc: bool = False


@dataclass
class MsTeamsConfig:
    enable: bool = False
    url: Optional[str] = None
    max_failed_send_attempts: int = 2


@dataclass
class AdcConfig:
    threshold_external_power: float = 2.5
    threshold_low_battery: float = 3.3


@dataclass
class Config:
    debug_mode_on: bool = False
    use_relay: bool = False
    prefix: str = field(default_factory=socket.gethostname)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    preview: PreviewConfig = field(default_factory=PreviewConfig)
    server_upload: ServerUploadConfig = field(default_factory=ServerUploadConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    wifi: WifiConfig = field(default_factory=WifiConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    msteams: MsTeamsConfig = field(default_factory=MsTeamsConfig)
    adc: AdcConfig = field(default_factory=AdcConfig)
    template_html_path: str = "~/OTCamera/webfiles/template.html"
    index_html_path: str = "~/OTCamera/webfiles/index.html"
    offline_html_path: str = "~/OTCamera/webfiles/offline.html"
    num_log_files_html: int = 2
    usb_mount_point: str = "~/mnt/usb"
    usb_device: str = "/dev/sda1"
    otcamera_version: Optional[str] = field(default=None, init=False)

    def resolve_paths(self) -> None:
        """Resolve ~ and relative paths to absolute paths."""
        self.video.dir = str(Path(self.video.dir).expanduser().resolve())
        self.preview.path = str(Path(self.preview.path).expanduser().resolve())
        self.template_html_path = str(
            Path(self.template_html_path).expanduser().resolve()
        )
        self.index_html_path = str(Path(self.index_html_path).expanduser().resolve())
        self.offline_html_path = str(
            Path(self.offline_html_path).expanduser().resolve()
        )
        self.usb_mount_point = str(Path(self.usb_mount_point).expanduser().resolve())
        self._read_version()

    def _read_version(self) -> None:
        """Read OTCamera version from ~/otcamera_version.txt if it exists."""
        version_path = Path("~/otcamera_version.txt").expanduser().resolve()
        if version_path.exists():
            self.otcamera_version = version_path.read_text().strip()


def _get(data: dict, key: str, default: object = None) -> object:  # type: ignore
    """Safely get a value from a dict, logging missing keys."""
    try:
        return data[key]
    except KeyError:
        logger.warning("Missing config key: '%s', using default", key)
        return default


def parse_user_config(config_file: str) -> Config:
    """Parse YAML config file and return a Config instance.

    Args:
        config_file: Path to the YAML config file.

    Returns:
        Config instance with values from file, defaults for missing keys.
    """
    config_path = Path(config_file).expanduser().resolve()
    config = Config()

    try:
        with open(config_path, mode="rb") as f:
            data = yaml.load(f, Loader=SafeLoader)
    except FileNotFoundError:
        logger.warning("No user config found at %s, using defaults.", config_path)
        config.resolve_paths()
        return config

    if not data:
        config.resolve_paths()
        return config

    # General
    section = data.get("debug_mode", {})
    config.debug_mode_on = bool(_get(section, "enable", config.debug_mode_on))

    section = data.get("relay_server", {})
    config.use_relay = bool(_get(section, "enable", config.use_relay))

    # Recording
    section = data.get("recording", {})
    r = config.recording
    r.start_hour = int(_get(section, "start_hour", r.start_hour))  # type: ignore
    r.end_hour = int(_get(section, "end_hour", r.end_hour))  # type: ignore
    r.interval_length = int(_get(section, "interval_length", r.interval_length))  # type: ignore
    r.num_intervals = int(_get(section, "num_intervals", r.num_intervals))  # type: ignore
    r.min_free_space = int(_get(section, "min_free_space", r.min_free_space))  # type: ignore

    # Camera
    section = data.get("camera", {})
    c = config.camera
    c.type = str(_get(section, "type", c.type))
    c.fps = int(_get(section, "fps", c.fps))  # type: ignore
    res = section.get("resolution", {})
    if res:
        c.resolution = (int(res.get("width", c.resolution[0])), int(res.get("height", c.resolution[1])))
    c.exposure_mode = str(_get(section, "exposure_mode", c.exposure_mode))
    c.drc_strength = str(_get(section, "drc_strength", c.drc_strength))
    c.rotation = int(_get(section, "rotation", c.rotation))  # type: ignore
    c.awb_mode = str(_get(section, "awb_mode", c.awb_mode))
    c.meter_mode = str(_get(section, "meter_mode", c.meter_mode))

    # Preview
    section = data.get("preview", {})
    p = config.preview
    p.path = str(_get(section, "path", p.path))
    p.format = str(_get(section, "format", p.format))
    p.interval = int(_get(section, "interval", p.interval))  # type: ignore
    p.send_to_external = bool(_get(section, "send_to_external", p.send_to_external))
    p.url = str(_get(section, "url", p.url))

    # Server upload
    section = data.get("server_upload", {})
    s = config.server_upload
    s.upload = bool(_get(section, "upload", s.upload))
    s.scheme = str(_get(section, "scheme", s.scheme))
    s.host = str(_get(section, "host", s.host))
    s.port = int(_get(section, "port", s.port))  # type: ignore
    s.user = str(_get(section, "user", s.user))
    s.password = str(_get(section, "password", s.password))
    s.server_source = str(_get(section, "server_source", s.server_source))

    # Video
    section = data.get("video", {})
    v = config.video
    v.dir = str(_get(section, "dir", v.dir))
    v.format = str(_get(section, "format", v.format))  # type: ignore
    res = section.get("resolution", {})
    if res:
        v.resolution = (int(res.get("width", v.resolution[0])), int(res.get("height", v.resolution[1])))
    enc = section.get("encoder", {})
    if enc:
        v.h264_profile = str(_get(enc, "profile", v.h264_profile))  # type: ignore
        v.h264_level = str(_get(enc, "level", v.h264_level))
        v.h264_bitrate = int(_get(enc, "bitrate", v.h264_bitrate))  # type: ignore
        v.h264_quality = int(_get(enc, "quality", v.h264_quality))  # type: ignore

    # Wifi
    section = data.get("wifi", {})
    config.wifi.delay = int(_get(section, "delay", config.wifi.delay))  # type: ignore

    # Hardware (includes enable toggles for BSL components)
    section = data.get("hardware", {})
    hw = config.hardware
    hw.pcb_version = str(  # type: ignore
        _get(section, "pcb_version", hw.pcb_version)
    )
    hw.use_leds = bool(_get(section, "use_leds", hw.use_leds))
    hw.use_buttons = bool(_get(section, "use_buttons", hw.use_buttons))
    hw.use_adc = bool(_get(section, "use_adc", hw.use_adc))

    # Legacy config key migration: old top-level sections → hardware toggles
    # (only applied if the new hardware.use_* keys were not explicitly set)
    if "use_leds" not in section:
        leds_section = data.get("leds", {})
        if "enable" in leds_section:
            hw.use_leds = bool(leds_section["enable"])
    if "use_buttons" not in section:
        buttons_section = data.get("buttons", {})
        if "enable" in buttons_section:
            hw.use_buttons = bool(buttons_section["enable"])
    if "use_adc" not in section:
        adc_legacy = data.get("adc", {})
        if "enable" in adc_legacy:
            hw.use_adc = bool(adc_legacy["enable"])

    # MS Teams
    section = data.get("msteams", {})
    config.msteams.enable = bool(_get(section, "enable", config.msteams.enable))
    config.msteams.url = _get(section, "url", config.msteams.url)  # type: ignore

    # ADC (thresholds only — hardware params are in board definitions)
    section = data.get("adc", {})
    config.adc.threshold_external_power = float(
        _get(section, "threshold_external_power", config.adc.threshold_external_power)  # type: ignore
    )
    config.adc.threshold_low_battery = float(
        _get(section, "threshold_low_battery", config.adc.threshold_low_battery)  # type: ignore
    )

    config.resolve_paths()
    return config


# Global config instance — set by __main__.py after parsing
CONFIG: Config = Config()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/config.py tests/test_config.py
git commit -m "refactor: rewrite config as validated dataclass with BSL-aware hardware section"
```

---

### Task 9: Refactor log.py (remove name.py and old config dependencies)

**Files:**
- Rewrite: `OTCamera/helpers/log.py`

After Task 8, `log.py` is broken: it imports `from OTCamera.helpers import name` (deleted
in cleanup) and `from OTCamera.config import DEBUG_MODE_ON, ...` (old module-level vars
replaced by Config dataclass). The module also runs code at import time (opens logfile),
which depends on config values. Fix by adding an `init(config)` function and inlining
the two `name.py` functions used (`_current_dt()` and `log()`).

- [ ] **Step 1: Rewrite log.py**

```python
# OTCamera/helpers/log.py
"""OTCamera helper for logging.

Open a logfile, based on the name.log and write a message to it. Also prints all
messages.

Use log.init(config) to initialize, then log.write(msg) to write any message,
log.breakline() to write a single line of # or log.otc() to log and print a
OpenTrafficCam logo.
"""

import json
import traceback
from datetime import datetime as dt
from enum import Enum
from pathlib import Path
from typing import Optional

import requests

from OTCamera.config import Config


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    EXCEPTION = "EXCEPTION"

    def __str__(self) -> str:
        return str(self.value)


# Module state — set by init()
_logf: Optional[object] = None
_config: Optional[Config] = None
_failed_attempts: int = 0
_disable_ms_teams_on_failed_attempts: bool = False


def _current_dt() -> str:
    """Generate current date and time string."""
    return dt.now().strftime("%Y-%m-%d_%H-%M-%S")


def _log_path(config: Config) -> Path:
    """Generate logfile path from config."""
    filename = (
        Path(config.video.dir)
        / f"{config.prefix}_FR{config.camera.fps}_{_current_dt()}.log"
    )
    return filename.expanduser().resolve()


def init(config: Config) -> None:
    """Initialize logging. Must be called after config is parsed.

    Args:
        config: Application configuration.
    """
    global _logf, _config
    _config = config
    logfile = _log_path(config)
    logfile.parent.mkdir(parents=True, exist_ok=True)
    _logf = open(logfile, "a")
    otc()
    breakline()


def write(msg: str, level: LogLevel = LogLevel.INFO, reboot: bool = True) -> None:
    """Write any message to logfile.

    Args:
        msg: Message to be written.
        level: Log level.
        reboot: Perform reboot if logging fails. Defaults to True.
    """
    global _disable_ms_teams_on_failed_attempts, _failed_attempts

    if level == LogLevel.DEBUG:
        if not _config or not _config.debug_mode_on:
            return
    current_time = _current_dt()
    msg = f"{current_time} {level}: {msg}"
    _write(msg, reboot)

    if _config and _failed_attempts >= _config.msteams.max_failed_send_attempts:
        _disable_ms_teams_on_failed_attempts = True

    if (
        _config
        and _config.msteams.enable
        and level != LogLevel.DEBUG
        and _config.msteams.url
        and not _disable_ms_teams_on_failed_attempts
    ):
        _send_msg_to_ms_teams(msg, _config.msteams.url, current_time)
    if level == LogLevel.EXCEPTION:
        _write(_get_stack_trace(), reboot)


def _send_msg_to_ms_teams(msg: str, teams_url: str, time: str) -> None:
    headers = {"Content-Type": "application/json"}
    payload = {"text": msg}
    err_prefix = f"{time} {LogLevel.ERROR}: "

    global _failed_attempts

    try:
        response = requests.post(
            teams_url, headers=headers, data=json.dumps(payload), timeout=10
        )
        status_code = response.status_code
        if status_code in range(400, 600):
            err_msg = (
                f"{err_prefix}"
                f"Unable to send MS Teams message [Status Code {status_code}]"
            )
            _write(err_msg)
            _failed_attempts += 1
        else:
            _failed_attempts = 0

    except requests.exceptions.RequestException as e:
        _write_exception_msg(err_prefix, e)
        _failed_attempts += 1


def _write_exception_msg(
    err_prefix: str,
    exception: Exception,
) -> None:
    _write(f"{err_prefix} {exception}")


def _get_stack_trace() -> str:
    return traceback.format_exc()


def breakline(reboot: bool = True) -> None:
    """Write a breakline containing several # to the logfile."""
    msg = "\n############################\n"
    _write(msg)


def otc() -> None:
    """Generate a ASCII logo and write it to the logfile."""
    from art import text2art

    otclogo = text2art("OpenTrafficCam")
    _write(otclogo)


def _write(msg: str, reboot: bool = True) -> None:
    print(msg)
    if _logf:
        _logf.write(msg + "\n")  # type: ignore[union-attr]
        _logf.flush()  # type: ignore[union-attr]


def closefile() -> None:
    """Flush and close the logfile."""
    if _logf:
        _logf.flush()  # type: ignore[union-attr]
        _logf.close()  # type: ignore[union-attr]
```

- [ ] **Step 2: Verify log module imports cleanly**

Run: `python -c "from OTCamera.helpers.log import LogLevel; print('OK')"`
Expected: prints OK (log.init() not called in tests, but log module imports cleanly)

Note: Full test suite (`pytest -v`) will NOT pass at this point — old modules
still import removed config module-level variables. Only task-specific tests
should be run until Task 21 (cleanup) is complete.

- [ ] **Step 3: Commit**

```bash
git add OTCamera/helpers/log.py
git commit -m "refactor: rewrite log.py to use Config dataclass, remove name.py dependency"
```

---

### Task 10: Board Protocol and board definitions

**Files:**
- Create: `OTCamera/bsl/boards/board.py`
- Create: `OTCamera/bsl/boards/v1.py`
- Create: `OTCamera/bsl/boards/v2.py`
- Create: `tests/bsl/__init__.py`
- Create: `tests/bsl/test_board_definitions.py`

Board definitions are frozen dataclasses — pure data, no logic. Each PCB version has one.
A `Board` Protocol enforces that all definitions share the same fields.

- [ ] **Step 1: Write the failing tests**

```python
# tests/bsl/test_board_definitions.py
import pytest

from OTCamera.bsl.boards.board import Board
from OTCamera.bsl.boards.v1 import BoardV1
from OTCamera.bsl.boards.v2 import BoardV2


class TestBoardDefinitions:
    def test_v1_satisfies_protocol(self) -> None:
        board: Board = BoardV1()
        assert board.led_power_pin >= 0
        assert board.adc_fsr > 0

    def test_v2_satisfies_protocol(self) -> None:
        board: Board = BoardV2()
        assert board.led_power_pin >= 0
        assert board.adc_fsr > 0

    def test_v1_is_frozen(self) -> None:
        board = BoardV1()
        with pytest.raises(AttributeError):
            board.led_power_pin = 99  # type: ignore[misc]

    def test_v2_is_frozen(self) -> None:
        board = BoardV2()
        with pytest.raises(AttributeError):
            board.led_power_pin = 99  # type: ignore[misc]

    def test_both_have_all_required_fields(self) -> None:
        required = [
            "led_power_pin", "led_wifi_pin", "led_rec_pin",
            "button_power_pin", "button_hour_pin", "button_wifi_pin",
            "button_power_pull_up", "button_hour_pull_up", "button_wifi_pull_up",
            "adc_i2c_address", "adc_fsr",
            "adc_channel_usb", "adc_channel_battery",
            "adc_divider_ratio_usb", "adc_divider_ratio_battery",
        ]
        for field_name in required:
            assert hasattr(BoardV1(), field_name), f"BoardV1 missing {field_name}"
            assert hasattr(BoardV2(), field_name), f"BoardV2 missing {field_name}"
```

- [ ] **Step 2: Create test package**

```bash
mkdir -p tests/bsl
touch tests/bsl/__init__.py
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/bsl/test_board_definitions.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement Board Protocol**

```python
# OTCamera/bsl/boards/board.py
"""Board protocol — structural typing contract for board definitions.

All board definitions must provide these fields. Using Protocol (structural
subtyping) instead of ABC so frozen dataclasses can satisfy it without
inheritance.
"""

from typing import Protocol


class Board(Protocol):
    """Contract for board definitions. All boards must provide these fields."""

    # LEDs (GPIO pin numbers)
    led_power_pin: int
    led_wifi_pin: int
    led_rec_pin: int

    # Buttons (GPIO pin numbers + pull-up config)
    button_power_pin: int
    button_hour_pin: int
    button_wifi_pin: int
    button_power_pull_up: bool
    button_hour_pull_up: bool
    button_wifi_pull_up: bool

    # ADC (I2C address, full-scale range, channel mapping, divider ratios)
    adc_i2c_address: int
    adc_fsr: float
    adc_channel_usb: int
    adc_channel_battery: int
    adc_divider_ratio_usb: float
    adc_divider_ratio_battery: float
```

- [ ] **Step 5: Implement BoardV1**

NOTE: Pin values below are from the original config defaults. Verify against actual
PCB v1 hardware before deploying.

```python
# OTCamera/bsl/boards/v1.py
"""Pin mappings and hardware parameters for PCB v1."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardV1:
    """Board definition for PCB v1."""

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

- [ ] **Step 6: Implement BoardV2**

```python
# OTCamera/bsl/boards/v2.py
"""Pin mappings and hardware parameters for PCB v2."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardV2:
    """Board definition for PCB v2."""

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

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/bsl/test_board_definitions.py -v`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add OTCamera/bsl/boards/ tests/bsl/
git commit -m "feat: add Board protocol and v1/v2 board definitions"
```

---

### Task 11: BSL implementations (LED, Button, ADC)

**Files:**
- Create: `OTCamera/bsl/led/pwm_led.py`
- Create: `OTCamera/bsl/button/gpio_button.py`
- Create: `OTCamera/bsl/adc/tla2024.py`

BSL implementations are generic — they implement domain ABCs and receive all board-specific
parameters via constructor injection. There is one implementation per component type, not
per PCB version. No unit tests for these (require Pi hardware).

- [ ] **Step 1: Implement PwmLed**

```python
# OTCamera/bsl/led/pwm_led.py
"""LED implementation using gpiozero PWMLED."""

from gpiozero import PWMLED

from OTCamera.domain.led import LED


class PwmLed(LED):
    """LED controlled via PWM on a GPIO pin.

    Args:
        pin: GPIO pin number.
    """

    def __init__(self, pin: int) -> None:
        self._led = PWMLED(pin)

    def on(self) -> None:
        self._led.on()

    def off(self) -> None:
        self._led.off()

    def blink(
        self,
        on_time: float = 0.1,
        off_time: float = 0.1,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        self._led.off()
        self._led.blink(
            on_time=on_time, off_time=off_time, n=n, background=background
        )

    def pulse(
        self,
        fade_in_time: float = 0.25,
        fade_out_time: float = 0.25,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        self._led.off()
        self._led.pulse(
            fade_in_time=fade_in_time,
            fade_out_time=fade_out_time,
            n=n,
            background=background,
        )
```

- [ ] **Step 2: Implement GpioButton**

```python
# OTCamera/bsl/button/gpio_button.py
"""Button implementation using gpiozero."""

from gpiozero import Button as GpioZeroButton

from OTCamera.domain.button import Button
from OTCamera.domain.events import ButtonHeld, ButtonPressed, ButtonReleased, EventBus


class GpioButton(Button):
    """Physical GPIO switch (toggle, not momentary).

    Construction creates the hardware object. bind() connects it to the
    event bus — called during wiring in __main__.py.

    gpiozero mapping for toggle switches:
    - when_pressed  = switch flipped to ON
    - when_held     = switch stayed ON for hold_time seconds
    - when_released = switch flipped to OFF

    Args:
        pin: GPIO pin number.
        pull_up: Enable internal pull-up resistor.
        hold_time: Seconds in ON position before triggering held event.
    """

    def __init__(
        self,
        pin: int,
        pull_up: bool = True,
        hold_time: float = 2.0,
    ) -> None:
        self._button = GpioZeroButton(
            pin, pull_up=pull_up, hold_time=hold_time, hold_repeat=False
        )

    def bind(self, name: str, event_bus: EventBus) -> None:
        """Register press/hold/release callbacks that emit named events."""
        self._button.when_pressed = lambda: event_bus.emit(
            ButtonPressed(name=name)
        )
        self._button.when_held = lambda: event_bus.emit(
            ButtonHeld(name=name)
        )
        self._button.when_released = lambda: event_bus.emit(
            ButtonReleased(name=name)
        )

    @property
    def is_pressed(self) -> bool:
        return bool(self._button.is_pressed)
```

- [ ] **Step 3: Implement TLA2024**

Copy the existing `OTCamera/plugin/adc/tla2024.py` to `OTCamera/bsl/adc/tla2024.py`.
The implementation and constructor are unchanged — only the file location changes.
The constructor accepts `i2c_address` and `fsr` via injection (set by BoardProvider).

```python
# OTCamera/bsl/adc/tla2024.py
# Copy from OTCamera/plugin/adc/tla2024.py — same implementation, new location.
# Constructor: TLA2024(i2c_address: int = 0x48, fsr: float = 4.096)
# Implements domain ADC ABC.
```

Run: `cp OTCamera/plugin/adc/tla2024.py OTCamera/bsl/adc/tla2024.py`

- [ ] **Step 4: Commit**

```bash
git add OTCamera/bsl/led/ OTCamera/bsl/button/ OTCamera/bsl/adc/
git commit -m "feat: add BSL implementations (PwmLed, GpioButton, TLA2024)"
```

---

### Task 12: BoardProvider

**Files:**
- Create: `OTCamera/bsl/board_provider.py`
- Create: `tests/bsl/test_board_provider.py`

The BoardProvider is the single entry point for all BSL components. It reads
`hardware.pcb_version` from config, loads the board definition, and instantiates
all BSL components with the correct parameters. Returns a `BoardComponents` bundle.

- [ ] **Step 1: Write the failing tests**

```python
# tests/bsl/test_board_provider.py
import pytest

from OTCamera.bsl.board_provider import load_board_definition


class TestBoardProvider:
    def test_unknown_pcb_version_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown PCB version"):
            load_board_definition("v99")

    def test_v1_loads(self) -> None:
        board = load_board_definition("v1")
        assert board.led_power_pin >= 0

    def test_v2_loads(self) -> None:
        board = load_board_definition("v2")
        assert board.led_power_pin >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bsl/test_board_provider.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement BoardProvider**

```python
# OTCamera/bsl/board_provider.py
"""Board provider — single entry point for all BSL components.

Reads pcb_version from config, loads the corresponding board definition,
and instantiates all BSL components with the correct parameters.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from OTCamera.bsl.boards.board import Board
from OTCamera.bsl.boards.v1 import BoardV1
from OTCamera.bsl.boards.v2 import BoardV2
from OTCamera.config import Config
from OTCamera.domain.adc import ADC, ADCConfig
from OTCamera.domain.button import Button
from OTCamera.domain.led import LED

logger = logging.getLogger(__name__)

# Board registry: maps pcb_version string to board definition class
_BOARD_REGISTRY: Dict[str, type] = {
    "v1": BoardV1,
    "v2": BoardV2,
}


@dataclass
class BoardComponents:
    """All hardware components and parameters provided by the board."""

    leds: Dict[str, LED]
    buttons: Dict[str, Button]
    adc: Optional[ADC]
    adc_config: Optional[ADCConfig]


def load_board_definition(pcb_version: str) -> Board:
    """Load board definition by PCB version string.

    Public so that external modules (e.g. usb_flash_drive_copy.py) can look up
    board-specific pin mappings without instantiating full BSL components.
    """
    if pcb_version not in _BOARD_REGISTRY:
        raise ValueError(
            f"Unknown PCB version: {pcb_version!r}. "
            f"Available: {list(_BOARD_REGISTRY.keys())}"
        )
    return _BOARD_REGISTRY[pcb_version]()


class BoardProvider:
    """Instantiates all BSL components for the configured PCB version."""

    @staticmethod
    def provide(config: Config) -> BoardComponents:
        """Create all board-specific components based on config.

        Args:
            config: Application configuration.

        Returns:
            BoardComponents bundle with LEDs, buttons, ADC, and ADCConfig.
        """
        board = load_board_definition(config.hardware.pcb_version)
        logger.info("Loaded board definition: PCB %s", config.hardware.pcb_version)

        leds: Dict[str, LED] = {}
        buttons: Dict[str, Button] = {}
        adc: Optional[ADC] = None
        adc_config: Optional[ADCConfig] = None

        # Set gpiozero pin factory if any GPIO components are needed
        needs_gpio = config.hardware.use_leds or config.hardware.use_buttons
        if needs_gpio:
            from gpiozero import Device
            from gpiozero.pins.lgpio import LGPIOFactory

            Device.pin_factory = LGPIOFactory()

        if config.hardware.use_leds:
            from OTCamera.bsl.led.pwm_led import PwmLed

            leds = {
                "power": PwmLed(board.led_power_pin),
                "recording": PwmLed(board.led_rec_pin),
                "wifi": PwmLed(board.led_wifi_pin),
            }
            # Turn all LEDs off on init (known-good state after boot)
            for led in leds.values():
                led.off()
            logger.debug("LEDs initialized: %s", list(leds.keys()))

        if config.hardware.use_buttons:
            from OTCamera.bsl.button.gpio_button import GpioButton

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
            logger.debug("Buttons initialized: %s", list(buttons.keys()))

        if config.hardware.use_adc:
            from OTCamera.bsl.adc.tla2024 import TLA2024

            adc = TLA2024(board.adc_i2c_address, board.adc_fsr)
            adc_config = ADCConfig(
                channel_usb=board.adc_channel_usb,
                channel_battery=board.adc_channel_battery,
                divider_ratio_usb=board.adc_divider_ratio_usb,
                divider_ratio_battery=board.adc_divider_ratio_battery,
            )
            logger.debug("ADC initialized")

        return BoardComponents(
            leds=leds, buttons=buttons, adc=adc, adc_config=adc_config
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/bsl/test_board_provider.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/bsl/board_provider.py tests/bsl/test_board_provider.py
git commit -m "feat: add BoardProvider as single entry point for BSL components"
```

---

### Task 13: Drop picamerax, update camera provider

**Files:**
- Delete: `OTCamera/plugin/camera/picamerax.py`
- Modify: `OTCamera/plugin/camera/camera_provider.py`

- [ ] **Step 1: Delete picamerax**

```bash
rm OTCamera/plugin/camera/picamerax.py
```

- [ ] **Step 2: Update camera_provider.py**

Rewrite to accept Config, remove legacy branch:

```python
# OTCamera/plugin/camera/camera_provider.py
"""Provider that creates camera backend based on config."""

import logging
from typing import Optional

from OTCamera.config import Config
from OTCamera.domain.camera import Camera

logger = logging.getLogger(__name__)


class CameraProvider:
    """Creates a Camera instance based on config."""

    _instance: Optional[Camera] = None

    @classmethod
    def provide(cls, config: Config) -> Camera:
        """Return Camera instance (cached singleton).

        Args:
            config: Application configuration.

        Returns:
            Camera instance.
        """
        if cls._instance is not None:
            return cls._instance

        from picamera2 import Picamera2

        from OTCamera.plugin.camera.picamera2 import PiCamera2, load_tuning_with_drc

        c = config.camera
        tuning = load_tuning_with_drc(c.drc_strength)
        try:
            picam2 = Picamera2(tuning=tuning)
        except IndexError:
            raise RuntimeError(
                "No camera detected by libcamera. "
                "Check that the camera is connected and the interface is enabled."
            ) from None
        cls._instance = PiCamera2(
            picam2,
            frame_rate=c.fps,
            resolution=c.resolution,
            video_resolution=config.video.resolution,
            exposure_mode=c.exposure_mode,
            awb_mode=c.awb_mode,
            drc_strength=c.drc_strength,
            rotation=c.rotation,
            meter_mode=c.meter_mode,
        )
        logger.info("Camera initialized: picamera2")
        return cls._instance
```

- [ ] **Step 3: Update picamera2.py — remove old config dependency**

The `PiCamera2` class currently uses `from OTCamera import config` and references
module-level config variables as default parameter values (e.g. `config.FPS`,
`config.RESOLUTION`). After the refactor, these no longer exist.

Changes required:
- Remove `from OTCamera import config` import
- Remove all config-based default parameter values from `__init__` — all values
  are now passed explicitly by `CameraProvider`
- Fix the `split_recording()` fallback (lines 393–401) to use stored instance
  values instead of config module vars

```python
# OTCamera/plugin/camera/picamera2.py — only showing changed parts

# REMOVE this import:
# from OTCamera import config

# __init__ signature — remove all config.* defaults:
def __init__(
    self,
    picam2: Picamera2,
    frame_rate: int,
    resolution: tuple[int, int],
    video_resolution: tuple[int, int],
    exposure_mode: str,
    awb_mode: str,
    drc_strength: str,
    rotation: int,
    meter_mode: str,
) -> None:
    # ... body stays the same ...

# split_recording fallback — use instance values instead of config:
def split_recording(self, save_path: str) -> None:
    """Split the recording to a new file."""
    try:
        from picamera2.outputs import SplittableOutput
    except ImportError:
        SplittableOutput = None

    if SplittableOutput is not None and isinstance(
        self._splittable_output, SplittableOutput
    ):
        new_output = FileOutput(save_path)
        self._splittable_output.split_output(new_output)
    else:
        log.write(
            "SplittableOutput not available, using stop/start for split",
            level=log.LogLevel.WARNING,
        )
        self.stop_recording()
        self.start_recording(
            save_path,
            self._video_format,
            self._video_resolution,
            self._bitrate,
            self._h264_profile,
            self._h264_level,
            self._h264_quality,
        )
```

Note: The `split_recording` fallback needs `start_recording` parameters that are
passed at the first `start_recording` call. These must be stored as instance
variables in `start_recording()`:

```python
def start_recording(self, save_file, video_format, resolution,
                    bitrate, h264_profile, h264_level, h264_quality):
    # Store for split_recording fallback
    self._video_format = video_format
    self._video_resolution = resolution
    self._bitrate = bitrate
    self._h264_profile = h264_profile
    self._h264_level = h264_level
    self._h264_quality = h264_quality
    # ... rest of existing implementation ...
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: drop picamerax, simplify camera provider, decouple picamera2 from config"
```

---

### Task 14: Upload adapter (FTP)

**Files:**
- Create: `OTCamera/adapter/upload/ftp_upload.py`
- Create: `OTCamera/adapter/upload/upload_provider.py`

Upload is a software integration with an external system (FTP server), not hardware.
It lives in `adapter/` per the hardware-layer-separation design.

- [ ] **Step 1: Implement FtpUpload**

```python
# OTCamera/adapter/upload/ftp_upload.py
"""Upload implementation using FTPS."""

import logging
from ftplib import FTP_TLS
from pathlib import Path

from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class FtpUpload(Upload):
    """Upload files via FTPS to a remote server."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        server_source: str = "/",
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._server_source = server_source

    def upload(self, file_path: str) -> None:
        """Upload a file via FTPS.

        Args:
            file_path: Absolute path to the local file.
        """
        source = Path(file_path)
        dest = Path(self._server_source) / source.name

        logger.debug("File to upload: %s (size: %d bytes)", source, source.stat().st_size)

        client = self._connect()
        try:
            self._navigate_to_dir(client, dest.parent)
            with open(source, "rb") as f:
                client.storbinary(f"STOR {dest.name}", f)
            logger.info("Uploaded %s", source.name)
        finally:
            client.close()

    def is_available(self) -> bool:
        """Check if FTP server is reachable."""
        try:
            client = self._connect()
            client.close()
            return True
        except Exception:
            return False

    def _connect(self) -> FTP_TLS:
        """Create authenticated FTPS connection."""
        ftp = FTP_TLS()
        ftp.connect(self._host, self._port, timeout=30)
        ftp.login(self._user, self._password)
        ftp.prot_p()
        return ftp

    def _navigate_to_dir(self, client: FTP_TLS, path: Path) -> None:
        """Navigate to directory, creating it if needed."""
        client.cwd("/")
        for part in path.parts:
            if part == "/":
                continue
            try:
                client.cwd(part)
            except Exception:
                client.mkd(part)
                client.cwd(part)
```

- [ ] **Step 2: Implement UploadProvider**

```python
# OTCamera/adapter/upload/upload_provider.py
"""Provider that creates upload backend based on config."""

import logging
from typing import Optional

from OTCamera.config import Config
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadProvider:
    """Creates an Upload instance based on config, or None if disabled."""

    @staticmethod
    def provide(config: Config) -> Optional[Upload]:
        """Return Upload instance or None if upload is disabled.

        Args:
            config: Application configuration.

        Returns:
            Upload instance or None.
        """
        if not config.server_upload.upload:
            logger.debug("Upload disabled")
            return None

        from OTCamera.adapter.upload.ftp_upload import FtpUpload

        su = config.server_upload
        return FtpUpload(
            host=su.host,
            port=su.port,
            user=su.user,
            password=su.password,
            server_source=su.server_source,
        )
```

- [ ] **Step 3: Commit**

```bash
git add OTCamera/adapter/upload/
git commit -m "feat: add Upload adapter with FTP and UploadProvider"
```

---

### Task 15: CameraController (move to controller/, refactor)

**Files:**
- Create: `OTCamera/controller/camera_controller.py`
- Delete: `OTCamera/hardware/camera_controller.py`

This is the biggest refactor. The controller needs to:
- Accept Config, LEDs dict, and EventBus via constructor (no global imports)
- Absorb `helpers/name.py` functions (video filename, annotation, preview path)
- Absorb `helpers/filesystem.py` functions (delete_old_files, disk space)
- Emit events (RecordingStarted, RecordingSplit, RecordingStopped, PreviewCaptured)
- Remove FTP upload logic (upload controller subscribes to events instead)

- [ ] **Step 1: Create controller/camera_controller.py**

```python
# OTCamera/controller/camera_controller.py
"""Camera recording orchestration.

Handles start/stop/split recording, preview capture, disk space management,
and annotation text. Emits events for non-critical subscribers.
"""

import base64
import logging
import re
from datetime import datetime as dt
from pathlib import Path
from time import sleep
from typing import Dict, Optional, Union

import psutil
import requests
import urllib3

from OTCamera.config import Config
from OTCamera.domain.camera import Camera, CameraClosedError
from OTCamera.domain.events import (
    EventBus,
    PreviewCaptured,
    RecordingSplit,
    RecordingStarted,
    RecordingStopped,
)
from OTCamera.domain.led import LED

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


class CameraController:
    """Orchestrates camera recording lifecycle.

    Args:
        camera: Camera instance to control.
        config: Application configuration.
        event_bus: Event bus for emitting recording events.
        leds: Dict of named LED instances (may be empty).
    """

    def __init__(
        self,
        camera: Camera,
        config: Config,
        event_bus: EventBus,
        leds: Dict[str, LED],
    ) -> None:
        self._camera = camera
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._current_video_file: str = self._video_filename()
        self._interval_finished: bool = False
        self._current_interval: int = 0
        self._more_intervals: bool = True

    @property
    def is_recording(self) -> bool:
        return self._camera.is_recording

    @property
    def more_intervals(self) -> bool:
        return self._more_intervals

    @property
    def current_interval(self) -> int:
        return self._current_interval

    # --- Recording lifecycle ---

    def start_recording(self) -> None:
        """Start video recording if not already recording."""
        if self._camera.is_recording:
            return

        self.delete_old_files()
        self._set_annotation_text()
        self._current_video_file = self._video_filename()
        v = self._config.video
        self._camera.start_recording(
            save_file=self._current_video_file,
            video_format=v.format,
            resolution=v.resolution,
            bitrate=v.h264_bitrate,
            h264_profile=v.h264_profile,
            h264_level=v.h264_level,
            h264_quality=v.h264_quality,
        )
        logger.info("Started recording: %s", self._current_video_file)
        self._led_recording_on()
        self._event_bus.emit(RecordingStarted(filename=self._current_video_file))
        self._wait_recording(2)
        self.capture()

    def stop_recording(self) -> None:
        """Stop video recording if currently recording."""
        if self._camera.is_recording:
            self._camera.stop_recording()
            self._led_recording_off()
            logger.info("Stopped recording. Videos: %d", self._current_interval)
            self._event_bus.emit(RecordingStopped())

    def split_if_interval_ends(self) -> None:
        """Split the video file if the configured interval has elapsed."""
        if self._is_new_interval():
            logger.debug("New interval")
            self._split()
            self._interval_finished = False
            self._current_interval += 1
            num = self._config.recording.num_intervals
            if num > 0:
                self._more_intervals = self._current_interval < num
            if not self._more_intervals:
                logger.debug("Last interval reached")
        elif self._is_after_new_interval_minute():
            self._interval_finished = True
            logger.debug("Reset interval flag")
        self._wait_recording(0.5)
        self._set_annotation_text()

    def capture(self) -> None:
        """Capture a preview image if recording."""
        if not self._camera.is_recording:
            logger.warning("Cannot capture preview, camera not recording")
            return

        self._set_annotation_text()
        preview_path = self._preview_path()
        self._camera.capture(
            save_file=preview_path,
            image_format=self._config.preview.format,
            resolution=self._config.video.resolution,
        )
        logger.debug("Preview captured")
        self._try_send_preview(preview_path)
        self._event_bus.emit(PreviewCaptured(path=preview_path))

    def close(self) -> None:
        """Close the camera instance."""
        try:
            self._camera.close()
            logger.debug("Camera closed")
        except CameraClosedError:
            logger.debug("Camera already closed")

    def restart(self) -> None:
        """Restart the camera."""
        logger.info("Restarting camera")
        self._camera.reinitialize()

    # --- Filename generation (absorbed from helpers/name.py) ---

    def _video_filename(self) -> str:
        """Generate video filename with prefix, FPS, and timestamp."""
        c = self._config
        filename = (
            Path(c.video.dir)
            / f"{c.prefix}_FR{c.camera.fps}_{self._current_dt()}.h264"
        )
        return str(filename.expanduser().resolve())

    def _preview_path(self) -> str:
        """Return resolved preview image path."""
        return str(Path(self._config.preview.path).expanduser().resolve())

    def _annotate_text(self) -> str:
        """Generate annotation text with prefix and timestamp."""
        return dt.now().strftime(self._config.prefix + " %d.%m.%Y %H:%M:%S")

    @staticmethod
    def _current_dt() -> str:
        return dt.now().strftime("%Y-%m-%d_%H-%M-%S")

    def _set_annotation_text(self) -> None:
        self._camera.set_annotation_text(self._annotate_text())

    # --- Disk space management (absorbed from helpers/filesystem.py) ---

    def delete_old_files(self) -> None:
        """Delete oldest video files until enough disk space is available."""
        video_dir = Path(self._config.video.dir).expanduser().resolve()
        min_bytes = self._config.recording.min_free_space * 1024 * 1024 * 1024
        logger.debug("Checking disk space")

        while psutil.disk_usage(str(video_dir)).free <= min_bytes:
            video_paths = [f for f in video_dir.iterdir() if f.suffix != ".log"]
            if len(video_paths) <= 1:
                logger.error("No more files to delete in %s", video_dir)
                raise OSError(f"No space and no files to delete in {video_dir}")
            oldest = min(video_paths, key=lambda p: p.stat().st_ctime)
            oldest.unlink()
            logger.info("Deleted %s", oldest)

    # --- Interval logic ---

    def _is_interval_minute(self) -> bool:
        current_minute = dt.now().minute
        return (current_minute % self._config.recording.interval_length) == 0

    def _is_after_new_interval_minute(self) -> bool:
        return not (self._is_interval_minute() or self._interval_finished)

    def _is_new_interval(self) -> bool:
        return (
            self._is_interval_minute()
            and self._interval_finished
            and self._more_intervals
        )

    def _split(self) -> None:
        """Split recording to a new file and emit event."""
        previous_file = self._current_video_file
        new_file = self._video_filename()
        self._camera.split_recording(new_file)
        self._current_video_file = new_file
        logger.info("Split recording: %s", new_file)
        self._event_bus.emit(RecordingSplit(filename=previous_file))
        self.delete_old_files()

    def _wait_recording(self, timeout: Union[int, float] = 0) -> None:
        if self._camera.is_recording:
            self._camera.wait_recording(timeout)
        else:
            sleep(timeout)

    # --- LED helpers ---

    def _led_recording_on(self) -> None:
        led = self._leds.get("recording")
        if led:
            led.blink(on_time=0.1, off_time=4.9, n=None, background=True)

    def _led_recording_off(self) -> None:
        led = self._leds.get("recording")
        if led:
            led.pulse(fade_in_time=0.25, fade_out_time=0.25, n=4, background=True)

    # --- Preview send ---

    def _try_send_preview(self, preview_path: str) -> None:
        if not self._config.preview.send_to_external:
            return
        try:
            with open(preview_path, "rb") as f:
                image = base64.b64encode(f.read()).decode("utf-8")
            response = requests.post(
                self._config.preview.url,
                json={"frame": 0, "image": image},
                verify=False,
                stream=True,
            )
            if response.status_code != 200:
                logger.warning("Preview send failed: %d", response.status_code)
            logger.debug("Preview sent to external server")
        except Exception as e:
            logger.warning("Error sending preview: %s", e)
```

- [ ] **Step 2: Verify module imports**

Run: `python -c "from OTCamera.controller.camera_controller import CameraController; print('OK')"`
Expected: prints OK

Note: Full test suite will not pass — old modules still reference removed config
module-level variables. Run task-specific tests only until Task 21 (cleanup).

- [ ] **Step 3: Commit**

```bash
git add OTCamera/controller/camera_controller.py
git commit -m "feat: add new CameraController in controller layer"
```

---

### Task 16: PowerController (move to controller/, refactor)

**Files:**
- Create: `OTCamera/controller/power_controller.py`
- Delete: `OTCamera/hardware/power_controller.py`

The power controller needs to:
- Accept Config, EventBus, LEDs, ADC, and ADCConfig via constructor
- Use `ADCConfig` (from BoardProvider) for channel/divider params instead of config
- Use `config.adc` only for deployment-specific thresholds
- Absorb shutdown/reboot logic from `helpers/rpi.py`
- Emit events (BatteryLow, ExternalPowerConnected/Disconnected, ShutdownRequested)
- Handle power switch: ON = cancel shutdown, OFF = 5s countdown then shutdown

- [ ] **Step 1: Create controller/power_controller.py**

```python
# OTCamera/controller/power_controller.py
"""Power monitoring and system control.

Monitors battery/USB via ADC, emits power events, handles system shutdown.
Uses ADCConfig (from BoardProvider) for channel/divider parameters and
config.adc for deployment-specific thresholds.

Power switch behavior:
- Switch ON (ButtonPressed): cancel pending shutdown
- Switch OFF (ButtonReleased): start 5s countdown, then shutdown
- Re-switching ON within 5s cancels the shutdown
"""

import logging
from datetime import datetime as dt
from datetime import timedelta
from subprocess import call
from typing import Dict, Optional

from OTCamera.config import Config
from OTCamera.domain.adc import ADC, ADCConfig
from OTCamera.domain.events import (
    BatteryLow,
    ButtonPressed,
    ButtonReleased,
    EventBus,
    ExternalPowerConnected,
    ExternalPowerDisconnected,
    ShutdownRequested,
)
from OTCamera.domain.led import LED

logger = logging.getLogger(__name__)

_POWER_SHUTDOWN_DELAY = 5  # seconds


class PowerController:
    """Monitors power status via ADC and handles shutdown.

    Args:
        config: Application configuration (thresholds).
        event_bus: Event bus for power events.
        leds: Dict of named LED instances.
        adc: ADC instance, or None if not available.
        adc_config: Board-specific ADC parameters, or None if no ADC.
    """

    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        leds: Dict[str, LED],
        adc: Optional[ADC] = None,
        adc_config: Optional[ADCConfig] = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._adc = adc
        self._adc_config = adc_config
        self._external_power_connected = False
        self._battery_is_low = False
        self._power_off_time: Optional[dt] = None

        event_bus.subscribe(ButtonPressed, self._on_button_pressed)
        event_bus.subscribe(ButtonReleased, self._on_button_released)

        if adc and adc_config:
            self._external_power_connected = self.is_external_power
            # NOTE: low battery check is NOT done here. It is done in main()
            # after all components are wired, so that the shutdown path works
            # correctly (OTCamera must exist to handle ShutdownRequested).

    @property
    def has_adc(self) -> bool:
        return self._adc is not None

    @property
    def is_low_battery(self) -> bool:
        if not self._adc or not self._adc_config:
            return False
        voltage = self._adc.get_voltage(self._adc_config.channel_battery)
        return (
            voltage * self._adc_config.divider_ratio_battery
            < self._config.adc.threshold_low_battery
        )

    @property
    def is_external_power(self) -> bool:
        if not self._adc or not self._adc_config:
            return False
        voltage = self._adc.get_voltage(self._adc_config.channel_usb)
        return (
            voltage * self._adc_config.divider_ratio_usb
            > self._config.adc.threshold_external_power
        )

    @property
    def external_power_connected(self) -> bool:
        return self._external_power_connected

    @property
    def shutdown_active(self) -> bool:
        """Whether a shutdown countdown is in progress (power switch OFF)."""
        return self._power_off_time is not None

    def check_power_status(self) -> None:
        """Check power status and emit events. Called from main loop."""
        if not self._adc or not self._adc_config:
            return

        if self.is_low_battery and not self._battery_is_low:
            self._on_low_battery()

        was_connected = self._external_power_connected
        is_connected = self.is_external_power

        if is_connected and not was_connected:
            self._external_power_connected = True
            logger.info("External power connected")
            self._event_bus.emit(ExternalPowerConnected())
        elif not is_connected and was_connected:
            self._external_power_connected = False
            logger.warning("External power disconnected")
            self._event_bus.emit(ExternalPowerDisconnected())

    def check_power_button(self) -> None:
        """Check if power switch shutdown countdown has elapsed. Called from main loop."""
        if self._power_off_time is None:
            return
        if self._power_off_time + timedelta(seconds=_POWER_SHUTDOWN_DELAY) < dt.now():
            self._power_off_time = None
            self.shutdown(source="button")

    def _on_button_pressed(self, event: ButtonPressed) -> None:
        """Power switch flipped to ON — cancel pending shutdown."""
        if event.name != "power":
            return
        if self._power_off_time is not None:
            self._power_off_time = None
            logger.info("Shutdown cancelled — power switch back ON")
        power_led = self._leds.get("power")
        if power_led:
            n = 2 if self._external_power_connected else 1
            power_led.blink(on_time=0.1, off_time=0.1, n=n, background=True)

    def _on_button_released(self, event: ButtonReleased) -> None:
        """Power switch flipped to OFF — start 5s shutdown countdown."""
        if event.name != "power":
            return
        self._power_off_time = dt.now()
        logger.info("Power switch OFF — shutdown in %ds", _POWER_SHUTDOWN_DELAY)
        power_led = self._leds.get("power")
        if power_led:
            power_led.blink(on_time=0.1, off_time=0.4, n=None, background=True)

    def shutdown(self, source: str = "unknown") -> None:
        """Shut down the Raspberry Pi.

        Args:
            source: What triggered the shutdown (battery, button, ui, etc.)
        """
        logger.info("Shutdown requested by %s", source)
        power_led = self._leds.get("power")
        if power_led:
            power_led.on()

        if self._config.use_relay:
            call("sudo systemctl stop sshrelay.service", shell=True)
            logger.info("Stopped SSH relay")

        self._event_bus.emit(ShutdownRequested(source=source))

        if not self._config.debug_mode_on:
            call("sudo shutdown -h now", shell=True)

    def reboot(self) -> None:
        """Reboot the Raspberry Pi."""
        logger.info("Rebooting")
        power_led = self._leds.get("power")
        if power_led:
            power_led.blink(on_time=0.1, off_time=0.1, n=None, background=True)

        if self._config.use_relay:
            call("sudo systemctl stop sshrelay.service", shell=True)

        if not self._config.debug_mode_on:
            call("sudo reboot", shell=True)

    def _on_low_battery(self) -> None:
        self._battery_is_low = True
        logger.warning("Battery level is low!")
        self.shutdown(source="battery")
```

- [ ] **Step 2: Commit**

```bash
git add OTCamera/controller/power_controller.py
git commit -m "feat: add PowerController in controller layer with ADCConfig support"
```

---

### Task 17: WifiController

**Files:**
- Create: `OTCamera/controller/wifi_controller.py`

- [ ] **Step 1: Implement WifiController**

```python
# OTCamera/controller/wifi_controller.py
"""Wi-Fi control via button events.

Subscribes to button events and manages Wi-Fi AP state.
"""

import logging
import re
import subprocess
from datetime import datetime as dt
from datetime import timedelta
from subprocess import call
from typing import Dict

from OTCamera.config import Config
from OTCamera.domain.events import (
    ButtonHeld,
    ButtonReleased,
    EventBus,
    WifiOff,
    WifiOn,
)
from OTCamera.domain.led import LED

logger = logging.getLogger(__name__)


class WifiController:
    """Manages Wi-Fi AP state based on wifi switch events.

    Switch behavior:
    - Switch ON (held for hold_time): Wi-Fi turns on immediately
    - Switch OFF (released): 15min delay, then Wi-Fi off
    - Re-switching ON during delay cancels the off-timer

    Args:
        config: Application configuration.
        event_bus: Event bus for wifi/switch events.
        leds: Dict of named LED instances.
    """

    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        leds: Dict[str, LED],
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._wifi_on: bool = True
        self._switch_off_time: dt | None = None

        event_bus.subscribe(ButtonHeld, self._on_switch_held)
        event_bus.subscribe(ButtonReleased, self._on_switch_released)

    @property
    def wifi_on(self) -> bool:
        return self._wifi_on

    @property
    def switch_off_time(self) -> "dt | None":
        """Time when wifi switch was flipped OFF, or None if no pending off-timer."""
        return self._switch_off_time

    def init_from_switch(self, wifi_switch_on: bool) -> None:
        """Initialize Wi-Fi state based on physical switch position at boot.

        Args:
            wifi_switch_on: Whether the wifi switch is in the ON position at boot.
        """
        if wifi_switch_on:
            self.switch_on()
        else:
            self.switch_off()

    def switch_on(self) -> None:
        """Turn Wi-Fi AP on."""
        self._switch_off_time = None  # Cancel any pending off timer
        if not self._wifi_on:
            if not self._config.debug_mode_on:
                call("sudo rfkill unblock wlan", shell=True)
            if self._config.use_relay:
                call("sudo systemctl start sshrelay.service", shell=True)
                logger.info("Started SSH relay")
            self._wifi_on = True
            logger.info("Wi-Fi on")
            self._event_bus.emit(WifiOn())

        wifi_led = self._leds.get("wifi")
        if wifi_led:
            wifi_led.blink(on_time=0.1, off_time=4.9, n=None, background=True)

    def switch_off(self) -> None:
        """Turn Wi-Fi AP off."""
        if self._wifi_on:
            if not self._config.debug_mode_on:
                call("sudo rfkill block wlan", shell=True)
            if self._config.use_relay:
                call("sudo systemctl stop sshrelay.service", shell=True)
                logger.info("Stopped SSH relay")
            self._wifi_on = False
            logger.info("Wi-Fi off")
            self._event_bus.emit(WifiOff())

        wifi_led = self._leds.get("wifi")
        if wifi_led:
            wifi_led.pulse(fade_in_time=0.25, fade_out_time=0.25, n=4, background=True)

    def check_delayed_off(self) -> None:
        """Check if Wi-Fi should be turned off after delay. Called from main loop."""
        if self._switch_off_time is None:
            return
        if not self._wifi_on:
            return

        delay = timedelta(seconds=self._config.wifi.delay)
        if self._switch_off_time + delay < dt.now():
            self.switch_off()
            self._switch_off_time = None

    def _on_switch_held(self, event: ButtonHeld) -> None:
        """Wifi switch held ON for hold_time — turn wifi on."""
        if event.name != "wifi":
            return
        self.switch_on()

    def _on_switch_released(self, event: ButtonReleased) -> None:
        """Wifi switch flipped to OFF — start delay timer."""
        if event.name != "wifi":
            return
        self._switch_off_time = dt.now()
        wifi_led = self._leds.get("wifi")
        if wifi_led:
            wifi_led.blink(on_time=0.1, off_time=0.9, n=None, background=True)
        logger.info("Wi-Fi turning off in %d s", self._config.wifi.delay)

    @staticmethod
    def is_wifi_enabled(device: str = "wlan0") -> bool:
        """Check if Wi-Fi device is up."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", device],
                capture_output=True,
                text=True,
            )
            return bool(re.search("state up", result.stdout, re.IGNORECASE))
        except Exception:
            return False
```

- [ ] **Step 2: Commit**

```bash
git add OTCamera/controller/wifi_controller.py
git commit -m "feat: add WifiController in controller layer"
```

---

### Task 18: ScheduleController

**Files:**
- Create: `OTCamera/controller/schedule_controller.py`
- Create: `tests/controller/test_schedule_controller.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/controller/test_schedule_controller.py
from datetime import datetime
from unittest.mock import patch

import pytest

from OTCamera.config import Config
from OTCamera.controller.schedule_controller import ScheduleController
from OTCamera.domain.events import ButtonPressed, ButtonReleased, EventBus


class TestScheduleController:
    def test_should_record_within_hours(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)

        with patch.object(sc, "_current_hour", return_value=12):
            assert sc.should_record() is True

    def test_should_not_record_outside_hours(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)

        with patch.object(sc, "_current_hour", return_value=23):
            assert sc.should_record() is False

    def test_hour_switch_on_enables_24_7(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)

        # Switch flipped to ON
        bus.emit(ButtonPressed(name="hour"))

        with patch.object(sc, "_current_hour", return_value=23):
            assert sc.should_record() is True

    def test_hour_switch_off_restores_schedule(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)

        # Switch ON then OFF
        bus.emit(ButtonPressed(name="hour"))
        bus.emit(ButtonReleased(name="hour"))

        with patch.object(sc, "_current_hour", return_value=23):
            assert sc.should_record() is False

    def test_init_from_switch_on(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)
        sc.init_from_switch(True)

        with patch.object(sc, "_current_hour", return_value=23):
            assert sc.should_record() is True

    def test_init_from_switch_off(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)
        sc.init_from_switch(False)

        with patch.object(sc, "_current_hour", return_value=23):
            assert sc.should_record() is False

    def test_other_button_does_not_affect_schedule(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)

        bus.emit(ButtonPressed(name="wifi"))

        with patch.object(sc, "_current_hour", return_value=23):
            assert sc.should_record() is False

    def test_should_not_record_during_shutdown(self) -> None:
        config = Config()
        bus = EventBus()
        sc = ScheduleController(config, bus)
        sc.set_shutdown_active(True)

        with patch.object(sc, "_current_hour", return_value=12):
            assert sc.should_record() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/controller/test_schedule_controller.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement ScheduleController**

```python
# OTCamera/controller/schedule_controller.py
"""Recording schedule controller.

Determines whether the camera should be recording based on configured
time windows and hour switch overrides. Future: calendar-based scheduling.

Hour switch behavior:
- Switch ON (ButtonPressed): enable 24/7 recording mode
- Switch OFF (ButtonReleased): disable 24/7, return to scheduled hours
"""

import logging
from datetime import datetime as dt

from OTCamera.config import Config
from OTCamera.domain.events import ButtonPressed, ButtonReleased, EventBus

logger = logging.getLogger(__name__)


class ScheduleController:
    """Determines if recording should be active.

    Args:
        config: Application configuration.
        event_bus: Event bus (subscribes to hour switch events).
    """

    def __init__(self, config: Config, event_bus: EventBus) -> None:
        self._config = config
        self._24_7_mode: bool = False
        self._shutdown_active: bool = False

        event_bus.subscribe(ButtonPressed, self._on_switch_pressed)
        event_bus.subscribe(ButtonReleased, self._on_switch_released)

    @property
    def is_24_7_mode(self) -> bool:
        return self._24_7_mode

    @property
    def shutdown_active(self) -> bool:
        return self._shutdown_active

    def should_record(self) -> bool:
        """Check if recording should be active right now.

        Returns:
            True if within schedule (or 24/7 mode) and not shutting down.
        """
        if self._shutdown_active:
            return False

        if self._24_7_mode:
            return True

        hour = self._current_hour()
        r = self._config.recording
        return r.start_hour <= hour < r.end_hour

    def init_from_switch(self, hour_switch_on: bool) -> None:
        """Initialize 24/7 mode based on physical switch position at boot.

        Args:
            hour_switch_on: Whether the hour switch is in the ON position at boot.
        """
        self._24_7_mode = hour_switch_on
        if hour_switch_on:
            logger.info("Hour switch ON at boot — 24/7 mode enabled")

    def set_shutdown_active(self, active: bool) -> None:
        """Mark system as shutting down (stops recording)."""
        self._shutdown_active = active

    def _current_hour(self) -> int:
        """Return current hour. Separate method for testability."""
        return dt.now().hour

    def _on_switch_pressed(self, event: ButtonPressed) -> None:
        """Hour switch flipped to ON — enable 24/7 mode."""
        if event.name != "hour":
            return
        self._24_7_mode = True
        logger.info("Hour switch ON — 24/7 mode enabled")

    def _on_switch_released(self, event: ButtonReleased) -> None:
        """Hour switch flipped to OFF — return to scheduled hours."""
        if event.name != "hour":
            return
        self._24_7_mode = False
        logger.info("Hour switch OFF — scheduled mode restored")
```

- [ ] **Step 4: Create tests/controller/__init__.py if needed**

```bash
touch tests/controller/__init__.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/controller/test_schedule_controller.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add OTCamera/controller/schedule_controller.py tests/controller/
git commit -m "feat: add ScheduleController with time-based recording schedule"
```

---

### Task 19: UploadController

**Files:**
- Create: `OTCamera/controller/upload_controller.py`

- [ ] **Step 1: Implement UploadController**

```python
# OTCamera/controller/upload_controller.py
"""Upload controller that subscribes to recording events.

Uploads video files when recording splits to a new file.
"""

import logging
from typing import Optional

from OTCamera.domain.events import EventBus, RecordingSplit
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadController:
    """Subscribes to RecordingSplit events and uploads completed files.

    Args:
        event_bus: Event bus to subscribe to.
        upload: Upload backend, or None if disabled.
    """

    def __init__(self, event_bus: EventBus, upload: Optional[Upload] = None) -> None:
        self._upload = upload
        if upload:
            event_bus.subscribe(RecordingSplit, self._on_recording_split)
            logger.debug("Upload controller active")

    def _on_recording_split(self, event: RecordingSplit) -> None:
        """Handle RecordingSplit event by uploading the completed file."""
        if not self._upload:
            return
        try:
            logger.info("Uploading %s", event.filename)
            self._upload.upload(event.filename)
        except Exception as e:
            logger.warning("Upload failed: %s", e)
```

- [ ] **Step 2: Commit**

```bash
git add OTCamera/controller/upload_controller.py
git commit -m "feat: add UploadController subscribing to RecordingSplit events"
```

---

### Task 20: Rewrite __main__.py (wiring + main loop)

**Files:**
- Rewrite: `OTCamera/__main__.py`
- Delete: `OTCamera/status.py` (replaced by direct controller reads)
- Modify: `OTCamera/record.py` (keep get_log_files_sorted, move OTCamera class logic)

Wiring uses `BoardProvider.provide()` as single entry point for all BSL components,
`CameraProvider` for the swappable camera plugin, and `UploadProvider` for the upload
adapter. Buttons are bound to the event bus after creation.

No separate Status class — the OTCamera class reads directly from controllers and
builds the DTOs for the html_updater. This avoids duplicated state.

- [ ] **Step 1: Rewrite __main__.py**

```python
# OTCamera/__main__.py
"""OTCamera entry point.

Wires all components together and runs the main recording loop.
"""

import errno
import logging
import re
import signal
import sys
from datetime import datetime as dt
from datetime import timedelta
from pathlib import Path
from time import sleep
from typing import Any, Dict, Iterator

import psutil

from OTCamera.adapter.upload.upload_provider import UploadProvider
from OTCamera.bsl.board_provider import BoardProvider
from OTCamera.config import Config, parse_user_config
from OTCamera.controller.camera_controller import CameraController
from OTCamera.controller.power_controller import PowerController
from OTCamera.controller.schedule_controller import ScheduleController
from OTCamera.controller.upload_controller import UploadController
from OTCamera.controller.wifi_controller import WifiController
from OTCamera.domain.events import EventBus, ShutdownRequested
from OTCamera.domain.led import LED
from OTCamera.helpers import log
from OTCamera.html_updater import (
    ConfigDataObject,
    ConfigHtmlId,
    LogDataObject,
    LogHtmlId,
    StatusDataObject,
    StatusHtmlId,
    StatusWebsiteUpdater,
)
from OTCamera.plugin.camera.camera_provider import CameraProvider

logger = logging.getLogger(__name__)


class OTCamera:
    """Main application class orchestrating the recording loop."""

    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        camera_controller: CameraController,
        power_controller: PowerController,
        wifi_controller: WifiController,
        schedule_controller: ScheduleController,
        html_updater: StatusWebsiteUpdater,
        leds: Dict[str, LED],
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._camera = camera_controller
        self._power = power_controller
        self._wifi = wifi_controller
        self._schedule = schedule_controller
        self._html_updater = html_updater
        self._leds = leds
        self._shutdown = False
        self._preview_taken = False
        self._power_led_blinked = False

        signal.signal(signal.SIGTERM, self._execute_shutdown)

        # Subscribe to ShutdownRequested so that shutdown also works in
        # debug_mode (where sudo shutdown is skipped and SIGTERM never fires)
        event_bus.subscribe(ShutdownRequested, self._on_shutdown_requested)

        Path(config.video.dir).mkdir(exist_ok=True)

    def record(self) -> None:
        """Run the main recording loop."""
        log.breakline()
        log.write("Starting periodic record")
        self._send_alive_signal()

        try:
            while self._camera.more_intervals and not self._shutdown:
                try:
                    self._loop()
                except OSError as oe:
                    if oe.errno == errno.ENOSPC:
                        log.write(str(oe), level=log.LogLevel.EXCEPTION)
                        self._camera.delete_old_files()
                    else:
                        log.write("OSError occurred", level=log.LogLevel.ERROR)
                        raise

            log.write("Captured all intervals, stopping", level=log.LogLevel.INFO)
        except KeyboardInterrupt:
            log.write("Keyboard Interrupt, stopping", level=log.LogLevel.INFO)
        except Exception as e:
            log.write(f"{e}", level=log.LogLevel.EXCEPTION)
            raise
        finally:
            self._execute_shutdown()

    def _loop(self) -> None:
        """Single iteration of the main loop."""
        self._power.check_power_status()
        self._power.check_power_button()
        self._wifi.check_delayed_off()
        self._send_alive_signal()

        if self._schedule.should_record():
            self._camera.start_recording()
            self._camera.split_if_interval_ends()
            self._try_capture_preview()
        else:
            self._camera.stop_recording()
            self._update_html()
            sleep(0.5)

    def _send_alive_signal(self) -> None:
        """Blink power LED every 5 seconds as alive signal.

        Suppressed when shutdown countdown is active (noblink guard) so the
        shutdown warning blink pattern is not interrupted.
        """
        if self._power.shutdown_active or self._schedule.shutdown_active:
            return

        current_second = dt.now().second
        is_send_time = (current_second % 5) == 3
        power_led = self._leds.get("power")

        if is_send_time and not self._power_led_blinked:
            if power_led:
                n = 2 if self._power.external_power_connected else 1
                power_led.blink(on_time=0.1, off_time=0.1, n=n, background=True)
            self._power_led_blinked = True
        elif not is_send_time and self._power_led_blinked:
            self._power_led_blinked = False

    def _try_capture_preview(self) -> None:
        """Capture preview at configured interval if Wi-Fi is on."""
        current_second = dt.now().second
        interval = self._config.preview.interval
        offset = interval - 1
        is_preview_time = (current_second % interval) == offset
        should_capture = (
            is_preview_time
            and self._wifi.wifi_on
            and not self._preview_taken
        )

        if should_capture and not self._schedule.shutdown_active:
            self._camera.capture()
            self._update_html()
            self._preview_taken = True
        elif not is_preview_time and self._preview_taken:
            # Reset flag after leaving the preview time window.
            self._preview_taken = False

    # --- HTML status website ---

    def _update_html(self) -> None:
        """Update the status website with current state from controllers."""
        self._html_updater.update_info(
            status_info=self._get_status_data(),
            config_info=self._get_config_settings(),
            currently_recording=self._camera.is_recording,
            always_recording=self._schedule.is_24_7_mode,
            external_power_supply_connected=self._power.external_power_connected,
        )

    def _get_status_data(self) -> StatusDataObject:
        """Build StatusDataObject from controller state."""
        video_dir = Path(self._config.video.dir).expanduser().resolve()
        free_bytes = psutil.disk_usage(str(video_dir)).free
        free_gb = free_bytes / (1024 * 1024 * 1024)

        num_videos = len([
            f for f in video_dir.iterdir()
            if f.suffix == f".{self._config.video.format}"
        ]) if video_dir.is_dir() else 0

        time_until_wifi_off = "--:--:--"
        if self._wifi.switch_off_time is not None:
            wifi_delay = timedelta(seconds=self._config.wifi.delay)
            remaining = (self._wifi.switch_off_time + wifi_delay) - dt.now()
            total_seconds = remaining.total_seconds()
            if total_seconds > 0:
                hours, rem = divmod(total_seconds, 3600)
                minutes, seconds = divmod(rem, 60)
                time_until_wifi_off = (
                    f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
                )
            else:
                time_until_wifi_off = "00:00:00"

        return StatusDataObject(
            free_diskspace=(
                StatusHtmlId.FREE_DISKSPACE, f"{free_gb:.2f} GB"
            ),
            num_videos_recorded=(
                StatusHtmlId.NUM_VIDEOS_RECORDED, num_videos
            ),
            currently_recording=(
                StatusHtmlId.CURRENTLY_RECORDING, self._camera.is_recording
            ),
            low_battery=(
                StatusHtmlId.LOW_BATTERY, self._power.is_low_battery
            ),
            hour_button_active=(
                StatusHtmlId.HOUR_BUTTON_ACTIVE, self._schedule.is_24_7_mode
            ),
            external_power_supply_connected=(
                StatusHtmlId.EXT_POWER_SUPPLY_CONNECTED,
                self._power.external_power_connected,
            ),
            ms_teams_webhook_enabled=(
                StatusHtmlId.MS_TEAMS_WEBHOOK_ENABLED,
                self._config.msteams.enable,
            ),
            time_until_wifi_off=(
                StatusHtmlId.TIME_UNTIL_WIFI_OFF, time_until_wifi_off
            ),
        )

    def _get_config_settings(self) -> ConfigDataObject:
        """Build ConfigDataObject from config."""
        c = self._config
        return ConfigDataObject(
            debug_mode_on=(ConfigHtmlId.DEBUG_MODE_ON, c.debug_mode_on),
            start_hour=(ConfigHtmlId.START_HOUR, c.recording.start_hour),
            end_hour=(ConfigHtmlId.END_HOUR, c.recording.end_hour),
            interval_video_split=(
                ConfigHtmlId.INTERVAL_VIDEO_SPLIT, c.recording.interval_length
            ),
            num_intervals=(ConfigHtmlId.NUM_INTERVALS, c.recording.num_intervals),
            preview_interval=(ConfigHtmlId.PREVIEW_INTERVAL, c.preview.interval),
            min_free_space=(
                ConfigHtmlId.MIN_FREE_SPACE, c.recording.min_free_space
            ),
            prefix=(ConfigHtmlId.PREFIX, c.prefix),
            video_dir=(ConfigHtmlId.VIDEO_DIR, c.video.dir),
            preview_path=(ConfigHtmlId.PREVIEW_PATH, c.preview.path),
            template_html_path=(
                ConfigHtmlId.TEMPLATE_HTML_PATH, c.template_html_path
            ),
            index_html_path=(ConfigHtmlId.INDEX_HTML_PATH, c.index_html_path),
            fps=(ConfigHtmlId.FPS, c.camera.fps),
            resolution=(ConfigHtmlId.RESOLUTION, c.camera.resolution),
            exposure_mode=(ConfigHtmlId.EXPOSURE_MODE, c.camera.exposure_mode),
            drc_strength=(ConfigHtmlId.DRC_STRENGTH, c.camera.drc_strength),
            rotation=(ConfigHtmlId.ROTATION, c.camera.rotation),
            awb_mode=(ConfigHtmlId.AWB_MODE, c.camera.awb_mode),
            video_format=(ConfigHtmlId.VIDEO_FORMAT, c.video.format),
            preview_format=(ConfigHtmlId.PREVIEW_FORMAT, c.preview.format),
            res_of_saved_video_file=(
                ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE, c.video.resolution
            ),
            h264_profile=(ConfigHtmlId.H264_PROFILE, c.video.h264_profile),
            h264_level=(ConfigHtmlId.H264_LEVEL, c.video.h264_level),
            h264_bitrate=(ConfigHtmlId.H264_BITRATE, c.video.h264_bitrate),
            h264_quality=(ConfigHtmlId.H264_QUALITY, c.video.h264_quality),
            use_led=(ConfigHtmlId.USE_LED, c.hardware.use_leds),
            use_buttons=(ConfigHtmlId.USE_BUTTONS, c.hardware.use_buttons),
            wifi_delay=(ConfigHtmlId.WIFI_DELAY, c.wifi.delay),
        )

    def _get_log_info(self, start_idx: int, num: int) -> LogDataObject:
        """Build LogDataObject from recent log files."""
        log_dir = Path(self._config.video.dir).expanduser().resolve()
        sorted_logs = _get_log_files_sorted(log_dir.iterdir())
        recent = sorted_logs[start_idx:num]
        recent.reverse()

        log_data = ""
        for log_file_path in recent:
            log_data += f"File: {log_file_path}\n"
            with open(log_file_path, "r") as f:
                log_data += f.read()
                log_data += "\n"

        return LogDataObject(log_data=(LogHtmlId.LOG_DATA, log_data))

    def _on_shutdown_requested(self, event: ShutdownRequested) -> None:
        """Handle ShutdownRequested event (from PowerController).

        In normal mode, sudo shutdown sends SIGTERM which triggers
        _execute_shutdown. In debug_mode, sudo shutdown is skipped,
        so this handler ensures the software cleanup still happens.
        """
        self._execute_shutdown()

    def _execute_shutdown(self, *args: Any) -> None:
        """Clean shutdown sequence — software cleanup only, no process exit.

        Sets ``self._shutdown = True`` which causes the ``record()`` loop
        to exit on the next iteration.  The actual OS shutdown (if any) is
        handled by ``PowerController.shutdown()`` *after* the event returns.

        Called from:
        - SIGTERM handler (normal shutdown via sudo shutdown)
        - ShutdownRequested event handler (debug_mode fallback)
        - finally block in record() (normal exit / exception)

        Must NOT call ``sys.exit()`` — doing so would raise ``SystemExit``
        through the synchronous EventBus callback chain and prevent
        ``PowerController.shutdown()`` from reaching ``sudo shutdown -h now``.
        """
        if self._shutdown:
            return

        log.breakline()
        log.write("Stopping OTCamera", level=log.LogLevel.INFO)
        self._schedule.set_shutdown_active(True)
        self._camera.stop_recording()
        self._camera.close()
        log.write("OTCamera stopped", level=log.LogLevel.INFO)
        log.breakline()
        self._shutdown = True
        # Note: display_offline_info BEFORE closefile (changed from old code which
        # did closefile first). This ensures log content is captured for the HTML page.
        self._html_updater.display_offline_info(
            self._get_log_info(0, self._config.num_log_files_html),
        )
        log.closefile()


def _get_log_files_sorted(log_files: Iterator[Path]) -> list[Path]:
    """Get log files sorted by timestamp in filename (newest first)."""
    regex = r"_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})"
    with_ts: list[tuple[dt, Path]] = []
    without_ts: list[Path] = []

    for f in log_files:
        if f.suffix != ".log":
            continue
        match = re.search(regex, f.stem)
        if match:
            ts = dt.strptime(match.group(1), "%Y-%m-%d_%H-%M-%S")
            with_ts.append((ts, f))
        else:
            without_ts.append(f)

    with_ts.sort(key=lambda e: e[0], reverse=True)
    return [f for _, f in with_ts] + without_ts


def main(config: "Config | None" = None, config_file: str = "~/user_config.yaml") -> None:
    """Wire up all components and start recording.

    Args:
        config: Pre-parsed Config object (from run.py). If None, parses config_file.
        config_file: Path to YAML config file (used only if config is None).
    """
    if config is None:
        config = parse_user_config(config_file)

    # Initialize logging (must be after config parse, before any log.write calls)
    log.init(config)

    if config.otcamera_version is not None:
        log.write(f"OTCamera Version: {config.otcamera_version}")

    event_bus = EventBus()

    # BSL — one call, all board-specific components as bundle
    board = BoardProvider.provide(config)

    # Plugin — independent of PCB version
    camera = CameraProvider.provide(config)

    # Adapter — software integrations
    upload = UploadProvider.provide(config)

    # Controllers — work against domain ABCs only
    camera_controller = CameraController(camera, config, event_bus, board.leds)
    power_controller = PowerController(
        config, event_bus, board.leds, board.adc, board.adc_config
    )
    wifi_controller = WifiController(config, event_bus, board.leds)
    schedule_controller = ScheduleController(config, event_bus)
    upload_controller = UploadController(event_bus, upload)  # noqa: F841

    # Wire buttons to event bus
    for name, button in board.buttons.items():
        button.bind(name, event_bus)

    # HTML updater
    html_updater = StatusWebsiteUpdater(
        template_html_path=config.template_html_path,
        offline_html_path=config.offline_html_path,
        html_save_path=config.index_html_path,
        status_info_id="status-info",
        config_info_id="config-info",
        log_info_id="log-info",
        debug_mode_on=config.debug_mode_on,
    )

    def _early_shutdown(source: str) -> None:
        """Cleanup and shutdown before OTCamera is created.

        Handles the case where we need to shut down during boot checks
        (power switch OFF, low battery) before the main OTCamera object
        exists to do its own cleanup.
        """
        camera.close()
        log.breakline()
        log.write(f"Early shutdown: {source}", level=log.LogLevel.INFO)
        log.breakline()
        html_updater.display_offline_info(
            LogDataObject(log_data=(LogHtmlId.LOG_DATA, "")),
        )
        log.closefile()
        power_controller.shutdown(source=source)

    # Boot check: if power switch is OFF at boot, shutdown immediately.
    # In debug_mode this just logs and returns (no recording started).
    if config.hardware.use_buttons and "power" in board.buttons:
        if not board.buttons["power"].is_pressed:
            _early_shutdown("boot")
            return

    # Boot check: if battery is already low at startup, shutdown immediately.
    if power_controller.has_adc and power_controller.is_low_battery:
        log.write("Battery low at startup!", level=log.LogLevel.WARNING)
        _early_shutdown("battery")
        return

    # Init Wi-Fi from switch state
    if config.hardware.use_buttons and "wifi" in board.buttons:
        wifi_controller.init_from_switch(board.buttons["wifi"].is_pressed)

    # Init hour switch: if ON at boot, enable 24/7 mode
    if config.hardware.use_buttons and "hour" in board.buttons:
        schedule_controller.init_from_switch(board.buttons["hour"].is_pressed)

    # Run
    otcamera = OTCamera(
        config=config,
        event_bus=event_bus,
        camera_controller=camera_controller,
        power_controller=power_controller,
        wifi_controller=wifi_controller,
        schedule_controller=schedule_controller,
        html_updater=html_updater,
        leds=board.leds,
    )
    otcamera.record()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update run.py**

Preserve the USB copy mode branching while using the new Config and entry point.
Pass `config` to `usb_flash_drive_copy.main()` so it can use the new Config dataclass.

```python
# run.py
"""CLI entry point for OTCamera.

Parses CLI args, loads config. If a USB device is present, copies videos
to USB; otherwise starts recording via OTCamera.__main__.main().
"""

import argparse
from pathlib import Path

from OTCamera.config import parse_user_config


def _parse_config_path() -> str:
    """Parse CLI args and return config file path."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="the absolute path to your custom config file.",
        required=False,
    )
    args = parser.parse_args()

    config_path = args.config or "~/user_config.yaml"

    if args.config is not None and not Path(args.config).exists():
        raise FileNotFoundError(f"The user config '{args.config}' does not exist.")

    return config_path


def main() -> None:
    config_path = _parse_config_path()
    config = parse_user_config(config_path)

    if Path(config.usb_device).exists():
        # USB flash drive detected — copy videos instead of recording
        import usb_flash_drive_copy

        usb_flash_drive_copy.main(config)
    else:
        # Normal mode — start recording
        from OTCamera.__main__ import main as otcamera_main

        otcamera_main(config=config)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Update usb_flash_drive_copy.py for new Config**

The USB copy module uses old module-level config variables (`config.USE_LED`,
`config.LED_POWER_PIN`, etc.) that no longer exist after the refactor. Update it to
accept a `Config` object and use `BoardProvider` for pin mappings.

```python
# usb_flash_drive_copy.py (update main() signature and build_usb_copier())
# Only showing the changed parts — rest of file stays the same.

# Replace: import OTCamera.config as config
from OTCamera.bsl.board_provider import load_board_definition
from OTCamera.config import Config
import OTCamera.helpers.log as log

# ... (Led, Button, CopyInformation, etc. classes stay the same,
# but remove all `config.USE_LED` / `config.DEBUG_MODE_ON` guards
# and replace with the passed-in config references)


def build_usb_copier(config: Config) -> OTCameraUsbCopier:
    """Builds a OTCameraUsbCopier object using the new Config dataclass."""
    src_dir = Path(config.video.dir)
    usb_flash_drive = UsbFlashDrive(Path(config.usb_mount_point))
    board = load_board_definition(config.hardware.pcb_version)

    if config.hardware.use_leds:
        power_led = Led(PWMLED(board.led_power_pin))
        rec_led = Led(PWMLED(board.led_rec_pin))
        wifi_led = Led(PWMLED(board.led_wifi_pin))
    else:
        # Create no-op LED wrappers that ignore all calls
        power_led = Led(None)  # type: ignore[arg-type]
        rec_led = Led(None)  # type: ignore[arg-type]
        wifi_led = Led(None)  # type: ignore[arg-type]

    usb_copier = OTCameraUsbCopier(
        power_led, wifi_led, rec_led, src_dir, usb_flash_drive,
        debug_mode_on=config.debug_mode_on,
    )

    if config.hardware.use_buttons:
        power_button = Button(
            "POWER",
            GPIOButton(
                board.button_power_pin,
                pull_up=board.button_power_pull_up,
                hold_time=2,
                hold_repeat=False,
            ),
        )
        power_button.attach(usb_copier)
    return usb_copier


def main(config: Config) -> None:
    """Start the OTCamera USB copy script.

    Args:
        config: Application configuration.
    """
    log.init(config)
    usb_device_mount = Path(config.usb_mount_point)
    src_dir = Path(config.video.dir)
    dest_dir = Path(usb_device_mount, get_hostname())
    usb_copier = build_usb_copier(config)
    usb_copy_info_path = CopyInformation.get_copy_info_csv(dest_dir)

    try:
        usb_copier.mount_usb_device()
        if usb_copy_info_path.exists():
            usb_copy_info = CopyInformation.from_csv(
                usb_copy_info_path, src_dir, dest_dir
            )
        else:
            usb_copy_info = CopyInformation.create_new(src_dir, dest_dir, "h264")

        usb_copier.copy_to_usb(usb_copy_info)
        usb_copier.delete(usb_copy_info)
        usb_copier.write_copy_info(usb_copy_info)
        usb_copier.unmount_usb_device()

        if config.hardware.use_buttons:
            while not usb_copier.shutdown_requested:
                continue
            usb_copier.shutdown()

    except Exception as e:
        log.write(str(e), log.LogLevel.EXCEPTION)
```

Also apply the following changes to existing classes in `usb_flash_drive_copy.py`:

**Led class** — replace `config.USE_LED` guards with null-safe checks. Keep
`time.sleep(2)` calls after `blink()` and `turn_on()` — these pauses are intentional
to give the user time to see the LED pattern before the next action starts.
Keep the original `blink()` signature (`times`, `background`) — no callers use
`on_time`/`off_time` in this module; gpiozero defaults (1s/1s) are correct.

```python
class Led:
    def __init__(self, led: "PWMLED | None") -> None:
        self._led = led

    def blink(self, times: Union[int, None] = None, background: bool = True) -> None:
        if self._led is not None:
            self._led.blink(n=times, background=background)
        time.sleep(2)

    def turn_off(self) -> None:
        if self._led is not None:
            self._led.off()

    def turn_on(self) -> None:
        if self._led is not None:
            self._led.on()
        time.sleep(2)
```

**OTCameraUsbCopier** — pass `debug_mode_on` so `shutdown()` and `delete()` can
check it (replaces `config.DEBUG_MODE_ON`):

```python
class OTCameraUsbCopier(Observer):
    def __init__(
        self,
        power_led: Led,
        wifi_led: Led,
        rec_led: Led,
        src_dir: Path,
        usb_flash_drive: UsbFlashDrive,
        debug_mode_on: bool = False,
    ) -> None:
        # ... existing fields ...
        self.debug_mode_on = debug_mode_on

    def shutdown(self) -> None:
        """Shutdown OTCamera."""
        self._turn_off_all_leds()
        self.power_led.blink(times=4, background=False)
        self.power_led.turn_on()
        if not self.debug_mode_on:
            log.closefile()
            subprocess.call("sudo shutdown -h now", shell=True)

    def delete(self, copy_info: CopyInformation) -> None:
        # ... existing loop ...
        # Replace `config.DEBUG_MODE_ON` with `self.debug_mode_on`:
        if self.debug_mode_on:
            log.write("Debug mode on. Only mock deleting file.", log.LogLevel.DEBUG)
        else:
            # ... actual file deletion (unchanged) ...
```

**build_usb_copier** — pass `debug_mode_on` through:
```python
def build_usb_copier(config: Config) -> OTCameraUsbCopier:
    # ... existing LED/button setup ...
    usb_copier = OTCameraUsbCopier(
        power_led, wifi_led, rec_led, src_dir, usb_flash_drive,
        debug_mode_on=config.debug_mode_on,
    )
    # ... existing button setup ...
```

- [ ] **Step 4: Commit**

```bash
git add OTCamera/__main__.py run.py usb_flash_drive_copy.py
git commit -m "refactor: rewrite __main__.py with BSL/plugin/adapter wiring"
```

---

### Task 21: Cleanup — delete old files and directories

**Files to delete:**
- `OTCamera/hardware/` (entire directory)
- `OTCamera/plugin/adc/` (entire directory — moved to bsl/adc/)
- `OTCamera/plugin/led/` (if existed — now bsl/led/)
- `OTCamera/plugin/button/` (if existed — now bsl/button/)
- `OTCamera/plugin_ftp_server/` (entire directory — replaced by adapter/upload/)
- `OTCamera/helpers/name.py` (absorbed into CameraController)
- `OTCamera/helpers/filesystem.py` (absorbed into CameraController)
- `OTCamera/helpers/rpi.py` (absorbed into PowerController)
- `OTCamera/helpers/errors.py` (NoMoreFilesToDeleteError no longer used)
- `OTCamera/record.py` (logic moved to __main__.py)
- `OTCamera/status.py` (no longer needed — controllers queried directly)
- `OTCamera/domain/camera_errors.py` (if not already deleted)

- [ ] **Step 1: Delete old files**

```bash
rm -rf OTCamera/hardware/
rm -rf OTCamera/plugin/adc/
rm -rf OTCamera/plugin/led/
rm -rf OTCamera/plugin/button/
rm -rf OTCamera/plugin_ftp_server/
rm -f OTCamera/helpers/name.py
rm -f OTCamera/helpers/filesystem.py
rm -f OTCamera/helpers/rpi.py
rm -f OTCamera/helpers/errors.py
rm -f OTCamera/record.py
rm -f OTCamera/status.py
rm -f OTCamera/domain/camera_errors.py
```

Note: `OTCamera/plugin/camera/picamerax.py` was already deleted in Task 13.

- [ ] **Step 2: Remove empty __init__.py files if directories are empty**

Check `OTCamera/helpers/` — if only `log.py` and `__init__.py` remain, keep both.
Check `OTCamera/plugin/` — should only contain `plugin/camera/` now.

- [ ] **Step 3: Update any remaining imports across the codebase**

Search for old imports and fix:
```bash
grep -r "from OTCamera.hardware" OTCamera/ tests/
grep -r "from OTCamera.helpers.name" OTCamera/ tests/
grep -r "from OTCamera.helpers.filesystem" OTCamera/ tests/
grep -r "from OTCamera.helpers.rpi" OTCamera/ tests/
grep -r "from OTCamera.helpers.errors" OTCamera/ tests/
grep -r "from OTCamera.record" OTCamera/ tests/
grep -r "from OTCamera.plugin_ftp_server" OTCamera/ tests/
grep -r "from OTCamera.plugin.camera.picamerax" OTCamera/ tests/
grep -r "from OTCamera.plugin.adc" OTCamera/ tests/
grep -r "from OTCamera.plugin.led" OTCamera/ tests/
grep -r "from OTCamera.plugin.button" OTCamera/ tests/
grep -r "from OTCamera.status" OTCamera/ tests/
grep -r "from OTCamera import status" OTCamera/ tests/
grep -r "import config" OTCamera/ tests/
```

Fix all found references to point to new locations.

- [ ] **Step 4: Run tests**

Run: `pytest -v`
Expected: All tests pass (some old tests may need updating — see Task 22)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: delete old hardware/, helpers, plugin_ftp_server, plugin/adc, record.py"
```

---

### Task 22: Update existing tests

**Files:**
- Modify: `tests/helpers/name_test.py` — functions moved into CameraController; tests need rewriting to test CameraController methods or be deleted
- Modify: `tests/helpers/filesystem_test.py` — functions absorbed into CameraController; adapt tests
- Modify: `tests/hardware/camera_test.py` — tests CameraProvider singleton; update import path
- Modify: `tests/record_test.py` — tests OTCamera class; update imports and constructor
- Modify: `tests/html_updater_test.py` — tests are **already broken** against the current API (fixture creates `StatusWebsiteUpdater(debug_mode_on=True)` missing 3 required path args; `update_info()` called with wrong positional args). Rewrite to match current `StatusWebsiteUpdater` constructor and `update_info()` signature. Note: `html_updater.py` itself is NOT changed by this refactor
- Modify: `tests/otcamera_test.py` — placeholder test, update if it references old modules
- Modify: `tests/conftest.py` — if any fixtures reference old modules
- Modify: `pyproject.toml` — add `testpaths = ["tests"]` to exclude root-level scripts from pytest

- [ ] **Step 1: Update or rewrite each test file**

For each test file, update imports to point to new locations. For tests that test absorbed functionality (name generation, filesystem), either:
- Rewrite as tests against CameraController (with a mock Camera)
- Keep as standalone utility tests if the functions are still accessible

**html_updater_test.py specifics (pre-existing breakage, not caused by refactor):**
- `StatusWebsiteUpdater(debug_mode_on=True)` → needs `template_html_path`, `offline_html_path`, `html_save_path` (use test fixtures from `tests/resources/`)
- `html_updater.update_info(html_filepath, html_filepath, status_data, config_data)` → wrong signature, should be `update_info(status_info, config_info, currently_recording, always_recording, external_power_supply_connected)`
- `StatusDataObject` fixture: missing fields (`external_power_supply_connected`, `ms_teams_webhook_enabled`, `time_until_wifi_off`)
- `ConfigDataObject` fixture: verify all field names still match

- [ ] **Step 2: Exclude root-level scripts from pytest**

`hardware_test.py` (repo root) has a `_test.py` suffix that causes pytest to
collect it, but it is a standalone Pi hardware verification script, not a pytest
test. Add `testpaths` to prevent collection:

Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Run all tests**

Run: `pytest -v`
Expected: all PASS

- [ ] **Step 4: Run linting**

Run: `pre-commit run --all-files`
Fix any issues.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: update tests for new architecture, add testpaths config"
```

---

### Task 22b: Rewrite hardware_check.py (standalone Pi verification script)

`hardware_test.py` (repo root) is a standalone interactive CLI tool for hardware
bring-up on Pi — it is NOT a pytest test. The old version uses `picamerax` (being
removed), module-level `config.*` globals, and PCBv1-specific GPIO buttons
(`low_battery_button`, `external_power_button`) that are ADC readings on PCBv2.

This task renames it to `hardware_check.py` to eliminate naming ambiguity and
rewrites it to use the new architecture.

**Files:**
- Delete: `hardware_test.py`
- Create: `hardware_check.py`

- [ ] **Step 1: Rename and rewrite**

Delete `hardware_test.py` and create `hardware_check.py` with the following changes:
- Replace `picamerax.PiCamera()` with `CameraProvider.provide(config)` (picamera2 backend)
- Replace `from OTCamera import config` + `config.BUTTON_*_PIN` / `config.LED_*_PIN` with `BoardProvider.provide(config)` to get LEDs, buttons, and ADC from the board bundle
- Remove `low_battery_button` and `external_power_button` GPIO buttons — on PCBv2 these are ADC readings, not GPIO pins
- Add ADC test commands: show battery voltage, USB voltage, external power status, low battery status
- Load config via `parse_user_config()` → `Config` dataclass
- Update interactive CLI commands to match new architecture

- [ ] **Step 2: Test on Pi**

This script can only be tested on a Pi with connected hardware. Run:
```bash
python hardware_check.py
```
Verify each interactive command works with real hardware.

- [ ] **Step 3: Commit**

```bash
git add hardware_check.py
git rm hardware_test.py
git commit -m "refactor: rename hardware_test.py to hardware_check.py, update for new architecture"
```

---

### Task 23: Final verification

- [ ] **Step 1: Run full test suite**

```bash
pytest -v --tb=short
```

- [ ] **Step 2: Run linting and type checking**

```bash
pre-commit run --all-files
mypy OTCamera tests --config-file=pyproject.toml
```

- [ ] **Step 3: Verify directory structure matches design**

```bash
find OTCamera -type f -name "*.py" | sort
```

Expected structure:
```
OTCamera/
├── domain/
│   ├── camera.py           # Camera ABC + CameraClosedError
│   ├── adc.py              # ADC ABC + ADCConfig
│   ├── led.py              # LED ABC
│   ├── button.py           # Button ABC with bind()
│   ├── upload.py           # Upload ABC
│   └── events.py           # EventBus + event dataclasses
├── bsl/
│   ├── boards/
│   │   ├── board.py        # Board Protocol
│   │   ├── v1.py           # PCB v1 definition
│   │   └── v2.py           # PCB v2 definition
│   ├── board_provider.py   # BoardProvider + BoardComponents
│   ├── led/
│   │   └── pwm_led.py      # PwmLed (generic, pin injected)
│   ├── button/
│   │   └── gpio_button.py  # GpioButton (generic, pin/pull injected)
│   └── adc/
│       └── tla2024.py      # TLA2024 (I2C address/FSR injected)
├── plugin/
│   └── camera/
│       ├── camera_provider.py
│       └── picamera2.py
├── adapter/
│   └── upload/
│       ├── upload_provider.py
│       └── ftp_upload.py
├── controller/
│   ├── camera_controller.py
│   ├── power_controller.py
│   ├── wifi_controller.py
│   ├── schedule_controller.py
│   └── upload_controller.py
├── config.py
├── __main__.py
├── html_updater.py
├── helpers/
│   └── log.py
├── abstraction/
│   └── singleton.py
├── gui/
└── version.py
```

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final cleanup and lint fixes"
```
