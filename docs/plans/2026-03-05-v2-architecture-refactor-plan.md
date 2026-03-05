# v2 Architecture Refactor — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor OTCamera into clean layers (domain/plugin/controller) with event bus, hardware ABCs, and provider pattern for swappable components.

**Architecture:** Domain ABCs define contracts. Plugins implement hardware. Controllers orchestrate logic. EventBus connects non-critical communication. Config/Status are global singleton classes.

**Tech Stack:** Python 3.9+, gpiozero, picamera2, smbus2, psutil, pyyaml, beautifulsoup4, pytest

**Design doc:** `docs/plans/2026-03-05-v2-architecture-refactor-design.md`

---

### Task 1: Create branch and project scaffolding

**Files:**
- Create: `OTCamera/controller/__init__.py`
- Create: `OTCamera/plugin/led/__init__.py`
- Create: `OTCamera/plugin/button/__init__.py`
- Create: `OTCamera/plugin/upload/__init__.py`

**Step 1: Create branch from v2**

```bash
git checkout v2
git checkout -b v2-refactor
```

**Step 2: Create empty package directories**

```bash
mkdir -p OTCamera/controller
touch OTCamera/controller/__init__.py
mkdir -p OTCamera/plugin/led
touch OTCamera/plugin/led/__init__.py
mkdir -p OTCamera/plugin/button
touch OTCamera/plugin/button/__init__.py
mkdir -p OTCamera/plugin/upload
touch OTCamera/plugin/upload/__init__.py
```

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: scaffold new package directories for refactor"
```

---

### Task 2: Event bus (domain/events.py)

**Files:**
- Create: `OTCamera/domain/events.py`
- Create: `tests/domain/test_events.py`

**Step 1: Write the failing tests**

```python
# tests/domain/test_events.py
import pytest

from OTCamera.domain.events import (
    BatteryLow,
    ButtonHeld,
    ButtonPressed,
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

**Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_events.py -v`
Expected: FAIL (module not found)

**Step 3: Implement the event bus**

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

**Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_events.py -v`
Expected: all PASS

**Step 5: Commit**

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

**Step 1: Add CameraClosedError to camera.py**

Add at line 1 of `OTCamera/domain/camera.py`, before the Camera class:

```python
class CameraClosedError(Exception):
    pass
```

**Step 2: Update import in camera_controller.py**

Change:
```python
from OTCamera.domain.camera_errors import CameraClosedError
```
To:
```python
from OTCamera.domain.camera import CameraClosedError
```

**Step 3: Search for any other imports of camera_errors and update them**

Run: `grep -r "camera_errors" OTCamera/ tests/`

Update all found imports to use `from OTCamera.domain.camera import CameraClosedError`.

**Step 4: Delete camera_errors.py**

```bash
rm OTCamera/domain/camera_errors.py
```

**Step 5: Run existing tests**

Run: `pytest -v`
Expected: all existing tests pass

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: merge CameraClosedError into domain/camera.py"
```

---

### Task 4: LED domain ABC

**Files:**
- Create: `OTCamera/domain/led.py`
- Create: `tests/domain/test_led.py`

**Step 1: Write the failing test**

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

**Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_led.py -v`
Expected: FAIL (module not found)

**Step 3: Implement the LED ABC**

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

**Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_led.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add OTCamera/domain/led.py tests/domain/test_led.py
git commit -m "feat: add LED abstract interface"
```

---

### Task 5: Button domain ABC

**Files:**
- Create: `OTCamera/domain/button.py`
- Create: `tests/domain/test_button.py`

**Step 1: Write the failing test**

```python
# tests/domain/test_button.py
import pytest

from OTCamera.domain.button import Button
from OTCamera.domain.events import ButtonHeld, ButtonPressed, EventBus


class FakeButton(Button):
    def __init__(self, name: str, event_bus: EventBus) -> None:
        super().__init__(name, event_bus)
        self._pressed = False

    @property
    def is_pressed(self) -> bool:
        return self._pressed

    def simulate_press(self) -> None:
        self._pressed = True
        self._on_pressed()

    def simulate_hold(self) -> None:
        self._on_held()

    def simulate_release(self) -> None:
        self._pressed = False
        self._on_released()


class TestButtonABC:
    def test_press_emits_event(self) -> None:
        bus = EventBus()
        received: list[ButtonPressed] = []
        bus.subscribe(ButtonPressed, received.append)
        btn = FakeButton("power", bus)
        btn.simulate_press()
        assert len(received) == 1
        assert received[0].name == "power"

    def test_hold_emits_event(self) -> None:
        bus = EventBus()
        received: list[ButtonHeld] = []
        bus.subscribe(ButtonHeld, received.append)
        btn = FakeButton("wifi", bus)
        btn.simulate_hold()
        assert len(received) == 1
        assert received[0].name == "wifi"

    def test_cannot_instantiate_abc(self) -> None:
        bus = EventBus()
        with pytest.raises(TypeError):
            Button("test", bus)  # type: ignore[abstract]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_button.py -v`
Expected: FAIL (module not found)

**Step 3: Implement the Button ABC**

```python
# OTCamera/domain/button.py
"""Abstract Button interface.

Buttons detect physical presses/holds and emit events on the event bus.
Controllers subscribe to these events to implement behavior.
"""

from abc import ABC, abstractmethod

from OTCamera.domain.events import ButtonHeld, ButtonPressed, EventBus


class Button(ABC):
    """Abstract button that emits events on press/hold.

    Args:
        name: Identifier for this button (e.g., "power", "wifi", "hour").
        event_bus: The event bus to emit button events on.
    """

    def __init__(self, name: str, event_bus: EventBus) -> None:
        self._name = name
        self._event_bus = event_bus

    @property
    def name(self) -> str:
        return self._name

    @property
    @abstractmethod
    def is_pressed(self) -> bool:
        """Whether the button is currently pressed."""
        raise NotImplementedError

    def _on_pressed(self) -> None:
        """Call when button is pressed. Emits ButtonPressed event."""
        self._event_bus.emit(ButtonPressed(name=self._name))

    def _on_held(self) -> None:
        """Call when button is held. Emits ButtonHeld event."""
        self._event_bus.emit(ButtonHeld(name=self._name))

    def _on_released(self) -> None:
        """Call when button is released. Subclasses may override."""
        pass
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_button.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add OTCamera/domain/button.py tests/domain/test_button.py
git commit -m "feat: add Button abstract interface"
```

---

### Task 6: Upload domain ABC

**Files:**
- Create: `OTCamera/domain/upload.py`
- Create: `tests/domain/test_upload.py`

**Step 1: Write the failing test**

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

**Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_upload.py -v`
Expected: FAIL (module not found)

**Step 3: Implement the Upload ABC**

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

**Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_upload.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add OTCamera/domain/upload.py tests/domain/test_upload.py
git commit -m "feat: add Upload abstract interface"
```

---

### Task 7: Config dataclass

**Files:**
- Rewrite: `OTCamera/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing tests**

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
          type: picamera2
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
        leds:
          enable: true
        buttons:
          enable: true
        hardware:
          pcb_version: v2
        msteams:
          enable: false
          url: ""
        adc:
          enable: true
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
        assert config.camera.type == "picamera2"
        assert config.video.h264_profile == "high"
        assert config.adc.enabled is True
        assert config.hardware.pcb_version == "v2"

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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (imports not found)

**Step 3: Rewrite config.py as dataclass**

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
    type: Literal["picamera2"] = "picamera2"
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
    led_power_pin: int = 11
    led_wifi_pin: int = 12
    led_rec_pin: int = 13
    button_power_pin: int = 21
    button_hour_pin: int = 20
    button_wifi_pin: int = 19
    button_power_pull_up: bool = True


@dataclass
class MsTeamsConfig:
    enable: bool = False
    url: Optional[str] = None
    max_failed_send_attempts: int = 2


@dataclass
class AdcConfig:
    enabled: bool = False
    i2c_address: int = 0x48
    fsr: float = 4.096
    channel_usb: int = 0
    channel_battery: int = 2
    divider_ratio_usb: float = 2.0
    divider_ratio_battery: float = 1510 / 510
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
    leds_enabled: bool = False
    buttons_enabled: bool = False
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    msteams: MsTeamsConfig = field(default_factory=MsTeamsConfig)
    adc: AdcConfig = field(default_factory=AdcConfig)
    template_html_path: str = "~/OTCamera/webfiles/template.html"
    index_html_path: str = "~/OTCamera/webfiles/index.html"
    offline_html_path: str = "~/OTCamera/webfiles/offline.html"
    num_log_files_html: int = 2
    usb_mount_point: str = "~/mnt/usb"
    usb_device: str = "/dev/sda1"

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
    c.type = str(_get(section, "type", c.type))  # type: ignore
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

    # LEDs & Buttons
    section = data.get("leds", {})
    config.leds_enabled = bool(_get(section, "enable", config.leds_enabled))

    section = data.get("buttons", {})
    config.buttons_enabled = bool(_get(section, "enable", config.buttons_enabled))

    # Hardware
    section = data.get("hardware", {})
    config.hardware.pcb_version = str(  # type: ignore
        _get(section, "pcb_version", config.hardware.pcb_version)
    )

    # MS Teams
    section = data.get("msteams", {})
    config.msteams.enable = bool(_get(section, "enable", config.msteams.enable))
    config.msteams.url = _get(section, "url", config.msteams.url)  # type: ignore

    # ADC
    section = data.get("adc", {})
    config.adc.enabled = bool(_get(section, "enable", config.adc.enabled))

    config.resolve_paths()
    return config


# Global config instance — set by __main__.py after parsing
CONFIG: Config = Config()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add OTCamera/config.py tests/test_config.py
git commit -m "refactor: rewrite config as validated dataclass"
```

---

### Task 8: LED plugin (pwm_led + provider)

**Files:**
- Create: `OTCamera/plugin/led/pwm_led.py`
- Create: `OTCamera/plugin/led/led_provider.py`

**Step 1: Implement PwmLed**

```python
# OTCamera/plugin/led/pwm_led.py
"""LED implementation using gpiozero PWMLED."""

from gpiozero import PWMLED

from OTCamera.domain.led import LED


class PwmLed(LED):
    """LED controlled via PWM on a GPIO pin."""

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

**Step 2: Implement LEDProvider**

```python
# OTCamera/plugin/led/led_provider.py
"""Provider that creates named LEDs based on config."""

import logging
from typing import Dict

from OTCamera.config import Config
from OTCamera.domain.led import LED

logger = logging.getLogger(__name__)


class LEDProvider:
    """Creates a dict of named LED instances based on hardware config."""

    @staticmethod
    def provide(config: Config) -> Dict[str, LED]:
        """Return named LEDs or empty dict if disabled.

        Args:
            config: Application configuration.

        Returns:
            Dict mapping LED names ("power", "recording", "wifi") to LED instances.
        """
        if not config.leds_enabled:
            logger.debug("LEDs disabled")
            return {}

        from OTCamera.plugin.led.pwm_led import PwmLed

        hw = config.hardware
        leds = {
            "power": PwmLed(hw.led_power_pin),
            "recording": PwmLed(hw.led_rec_pin),
            "wifi": PwmLed(hw.led_wifi_pin),
        }
        logger.debug("LEDs initialized: %s", list(leds.keys()))
        return leds
```

**Step 3: Commit**

```bash
git add OTCamera/plugin/led/
git commit -m "feat: add LED plugin with PwmLed and LEDProvider"
```

---

### Task 9: Button plugin (gpio_button + provider)

**Files:**
- Create: `OTCamera/plugin/button/gpio_button.py`
- Create: `OTCamera/plugin/button/button_provider.py`

**Step 1: Implement GpioButton**

```python
# OTCamera/plugin/button/gpio_button.py
"""Button implementation using gpiozero."""

from gpiozero import Button as GpioZeroButton
from gpiozero import Device
from gpiozero.pins.lgpio import LGPIOFactory

from OTCamera.domain.button import Button
from OTCamera.domain.events import EventBus

Device.pin_factory = LGPIOFactory()


class GpioButton(Button):
    """Physical button on a GPIO pin.

    Emits ButtonPressed/ButtonHeld events via the event bus.
    """

    def __init__(
        self,
        name: str,
        pin: int,
        event_bus: EventBus,
        pull_up: bool = True,
        hold_time: float = 2,
    ) -> None:
        super().__init__(name, event_bus)
        self._button = GpioZeroButton(
            pin, pull_up=pull_up, hold_time=hold_time, hold_repeat=False
        )
        self._button.when_pressed = lambda: self._on_pressed()
        self._button.when_held = lambda: self._on_held()
        self._button.when_released = lambda: self._on_released()

    @property
    def is_pressed(self) -> bool:
        return bool(self._button.is_pressed)
```

**Step 2: Implement ButtonProvider**

```python
# OTCamera/plugin/button/button_provider.py
"""Provider that creates buttons based on config."""

import logging
from typing import Dict

from OTCamera.config import Config
from OTCamera.domain.button import Button
from OTCamera.domain.events import EventBus

logger = logging.getLogger(__name__)


class ButtonProvider:
    """Creates a dict of named Button instances based on hardware config."""

    @staticmethod
    def provide(config: Config, event_bus: EventBus) -> Dict[str, Button]:
        """Return named buttons or empty dict if disabled.

        Args:
            config: Application configuration.
            event_bus: Event bus for button events.

        Returns:
            Dict mapping button names to Button instances.
        """
        if not config.buttons_enabled:
            logger.debug("Buttons disabled")
            return {}

        from OTCamera.plugin.button.gpio_button import GpioButton

        hw = config.hardware
        buttons = {
            "power": GpioButton(
                "power",
                hw.button_power_pin,
                event_bus,
                pull_up=hw.button_power_pull_up,
            ),
            "hour": GpioButton("hour", hw.button_hour_pin, event_bus),
            "wifi": GpioButton("wifi", hw.button_wifi_pin, event_bus),
        }
        logger.debug("Buttons initialized: %s", list(buttons.keys()))
        return buttons
```

**Step 3: Commit**

```bash
git add OTCamera/plugin/button/
git commit -m "feat: add Button plugin with GpioButton and ButtonProvider"
```

---

### Task 10: Upload plugin (FTP)

**Files:**
- Create: `OTCamera/plugin/upload/ftp_upload.py`
- Create: `OTCamera/plugin/upload/upload_provider.py`

**Step 1: Implement FtpUpload**

```python
# OTCamera/plugin/upload/ftp_upload.py
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
        ftp.connect(self._host, self._port)
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

**Step 2: Implement UploadProvider**

```python
# OTCamera/plugin/upload/upload_provider.py
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

        from OTCamera.plugin.upload.ftp_upload import FtpUpload

        su = config.server_upload
        return FtpUpload(
            host=su.host,
            port=su.port,
            user=su.user,
            password=su.password,
            server_source=su.server_source,
        )
```

**Step 3: Commit**

```bash
git add OTCamera/plugin/upload/
git commit -m "feat: add Upload plugin with FTP and UploadProvider"
```

---

### Task 11: Drop picamerax, update camera provider

**Files:**
- Delete: `OTCamera/plugin/camera/picamerax.py`
- Modify: `OTCamera/plugin/camera/camera_provider.py`

**Step 1: Delete picamerax**

```bash
rm OTCamera/plugin/camera/picamerax.py
```

**Step 2: Update camera_provider.py**

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

        from OTCamera.plugin.camera.picamera2 import PiCamera2

        c = config.camera
        cls._instance = PiCamera2(
            framerate=c.fps,
            resolution=c.resolution,
            exposure_mode=c.exposure_mode,
            awb_mode=c.awb_mode,
            drc_strength=c.drc_strength,
            rotation=c.rotation,
            meter_mode=c.meter_mode,
        )
        logger.info("Camera initialized: picamera2")
        return cls._instance
```

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: drop picamerax, simplify camera provider"
```

---

### Task 12: Update ADC provider to accept Config

**Files:**
- Modify: `OTCamera/plugin/adc/adc_provider.py`

**Step 1: Update adc_provider.py**

```python
# OTCamera/plugin/adc/adc_provider.py
"""Provider that creates ADC backend based on config."""

import logging
from typing import Optional

from OTCamera.config import Config
from OTCamera.domain.adc import ADC

logger = logging.getLogger(__name__)


class ADCProvider:
    """Creates an ADC instance based on config, or None if disabled."""

    @staticmethod
    def provide(config: Config) -> Optional[ADC]:
        """Return ADC instance or None if disabled.

        Args:
            config: Application configuration.

        Returns:
            ADC instance or None.
        """
        if not config.adc.enabled:
            logger.debug("ADC disabled")
            return None

        from OTCamera.plugin.adc.tla2024 import TLA2024

        return TLA2024(
            i2c_address=config.adc.i2c_address,
            fsr=config.adc.fsr,
        )
```

**Step 2: Commit**

```bash
git add OTCamera/plugin/adc/adc_provider.py
git commit -m "refactor: update ADC provider to accept Config"
```

---

### Task 13: CameraController (move to controller/, refactor)

**Files:**
- Create: `OTCamera/controller/camera_controller.py`
- Delete: `OTCamera/hardware/camera_controller.py`

This is the biggest refactor. The controller needs to:
- Accept Config, LEDs dict, and EventBus via constructor (no global imports)
- Absorb `helpers/name.py` functions (video filename, annotation, preview path)
- Absorb `helpers/filesystem.py` functions (delete_old_files, disk space)
- Emit events (RecordingStarted, RecordingSplit, RecordingStopped, PreviewCaptured)
- Remove FTP upload logic (upload controller subscribes to events instead)

**Step 1: Create controller/camera_controller.py**

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

        self._delete_old_files()
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

    def _delete_old_files(self) -> None:
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
        self._delete_old_files()

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

**Step 2: Run existing tests**

Run: `pytest -v`
Expected: tests pass (old imports still exist at this point)

**Step 3: Commit**

```bash
git add OTCamera/controller/camera_controller.py
git commit -m "feat: add new CameraController in controller layer"
```

---

### Task 14: PowerController (move to controller/, refactor)

**Files:**
- Create: `OTCamera/controller/power_controller.py`
- Delete: `OTCamera/hardware/power_controller.py`

The power controller needs to:
- Accept Config, EventBus, and LEDs via constructor
- Absorb shutdown/reboot logic from `helpers/rpi.py`
- Emit events (BatteryLow, ExternalPowerConnected/Disconnected, ShutdownRequested)

**Step 1: Create controller/power_controller.py**

```python
# OTCamera/controller/power_controller.py
"""Power monitoring and system control.

Monitors battery/USB via ADC, emits power events, handles system shutdown.
"""

import logging
from subprocess import call
from typing import Dict, Optional

from OTCamera.config import Config
from OTCamera.domain.adc import ADC
from OTCamera.domain.events import (
    BatteryLow,
    EventBus,
    ExternalPowerConnected,
    ExternalPowerDisconnected,
    ShutdownRequested,
)
from OTCamera.domain.led import LED

logger = logging.getLogger(__name__)


class PowerController:
    """Monitors power status via ADC and handles shutdown.

    Args:
        config: Application configuration.
        event_bus: Event bus for power events.
        leds: Dict of named LED instances.
        adc: ADC instance, or None if not available.
    """

    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        leds: Dict[str, LED],
        adc: Optional[ADC] = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._adc = adc
        self._external_power_connected = False
        self._battery_is_low = False

        if adc:
            self._external_power_connected = self.is_external_power
            if self.is_low_battery:
                self._on_low_battery()

    @property
    def has_adc(self) -> bool:
        return self._adc is not None

    @property
    def is_low_battery(self) -> bool:
        if not self._adc:
            return False
        voltage = self._adc.get_voltage(self._config.adc.channel_battery)
        return voltage * self._config.adc.divider_ratio_battery < self._config.adc.threshold_low_battery

    @property
    def is_external_power(self) -> bool:
        if not self._adc:
            return False
        voltage = self._adc.get_voltage(self._config.adc.channel_usb)
        return voltage * self._config.adc.divider_ratio_usb > self._config.adc.threshold_external_power

    @property
    def external_power_connected(self) -> bool:
        return self._external_power_connected

    def check_power_status(self) -> None:
        """Check power status and emit events. Called from main loop."""
        if not self._adc:
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

**Step 2: Commit**

```bash
git add OTCamera/controller/power_controller.py
git commit -m "feat: add PowerController in controller layer"
```

---

### Task 15: WifiController

**Files:**
- Create: `OTCamera/controller/wifi_controller.py`

**Step 1: Implement WifiController**

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
from OTCamera.domain.events import ButtonHeld, ButtonPressed, EventBus, WifiOff, WifiOn
from OTCamera.domain.led import LED

logger = logging.getLogger(__name__)


class WifiController:
    """Manages Wi-Fi AP state based on button events.

    Args:
        config: Application configuration.
        event_bus: Event bus for wifi/button events.
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
        self._button_released_time: dt | None = None

        event_bus.subscribe(ButtonHeld, self._on_button_held)
        event_bus.subscribe(ButtonPressed, self._on_button_pressed)

    @property
    def wifi_on(self) -> bool:
        return self._wifi_on

    def init_from_button(self, wifi_button_pressed: bool) -> None:
        """Initialize Wi-Fi state based on physical button state at boot.

        Args:
            wifi_button_pressed: Whether the wifi button is pressed at boot.
        """
        if wifi_button_pressed:
            self.switch_on()
        else:
            self.switch_off()

    def switch_on(self) -> None:
        """Turn Wi-Fi AP on."""
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
        if self._button_released_time is None:
            return
        if not self._wifi_on:
            return

        delay = timedelta(seconds=self._config.wifi.delay)
        if self._button_released_time + delay < dt.now():
            self.switch_off()
            self._button_released_time = None

    def _on_button_held(self, event: ButtonHeld) -> None:
        if event.name != "wifi":
            return
        self._button_released_time = None
        self.switch_on()

    def _on_button_pressed(self, event: ButtonPressed) -> None:
        if event.name != "wifi":
            return
        # Button released (pressed again cancels pending off)
        # Note: ButtonPressed fires on press, release is tracked via timing
        self._button_released_time = dt.now()
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

**Step 2: Commit**

```bash
git add OTCamera/controller/wifi_controller.py
git commit -m "feat: add WifiController in controller layer"
```

---

### Task 16: ScheduleController

**Files:**
- Create: `OTCamera/controller/schedule_controller.py`
- Create: `tests/controller/test_schedule_controller.py`

**Step 1: Write the failing tests**

```python
# tests/controller/test_schedule_controller.py
from datetime import datetime
from unittest.mock import patch

import pytest

from OTCamera.config import Config
from OTCamera.controller.schedule_controller import ScheduleController
from OTCamera.domain.events import ButtonHeld, EventBus


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

    def test_hour_button_overrides_schedule(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)

        # Simulate hour button held
        bus.emit(ButtonHeld(name="hour"))

        with patch.object(sc, "_current_hour", return_value=23):
            assert sc.should_record() is True

    def test_hour_button_release_restores_schedule(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)

        # Hold then "release" (pressed event toggles off)
        bus.emit(ButtonHeld(name="hour"))
        sc.set_24_7_mode(False)

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

**Step 2: Run tests to verify they fail**

Run: `pytest tests/controller/test_schedule_controller.py -v`
Expected: FAIL (module not found)

**Step 3: Implement ScheduleController**

```python
# OTCamera/controller/schedule_controller.py
"""Recording schedule controller.

Determines whether the camera should be recording based on configured
time windows and button overrides. Future: calendar-based scheduling.
"""

import logging
from datetime import datetime as dt

from OTCamera.config import Config
from OTCamera.domain.events import ButtonHeld, EventBus

logger = logging.getLogger(__name__)


class ScheduleController:
    """Determines if recording should be active.

    Args:
        config: Application configuration.
        event_bus: Event bus (subscribes to hour button events).
    """

    def __init__(self, config: Config, event_bus: EventBus) -> None:
        self._config = config
        self._24_7_mode: bool = False
        self._shutdown_active: bool = False

        event_bus.subscribe(ButtonHeld, self._on_button_held)

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

    def set_24_7_mode(self, enabled: bool) -> None:
        """Set or clear 24/7 recording mode."""
        self._24_7_mode = enabled
        logger.info("24/7 mode: %s", "ON" if enabled else "OFF")

    def set_shutdown_active(self, active: bool) -> None:
        """Mark system as shutting down (stops recording)."""
        self._shutdown_active = active

    def _current_hour(self) -> int:
        """Return current hour. Separate method for testability."""
        return dt.now().hour

    def _on_button_held(self, event: ButtonHeld) -> None:
        if event.name == "hour":
            self._24_7_mode = True
            logger.info("Hour button held — 24/7 mode ON")
```

**Step 4: Create tests/__init__.py and tests/controller/__init__.py if needed**

```bash
touch tests/controller/__init__.py
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/controller/test_schedule_controller.py -v`
Expected: all PASS

**Step 6: Commit**

```bash
git add OTCamera/controller/schedule_controller.py tests/controller/
git commit -m "feat: add ScheduleController with time-based recording schedule"
```

---

### Task 17: UploadController

**Files:**
- Create: `OTCamera/controller/upload_controller.py`

**Step 1: Implement UploadController**

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

**Step 2: Commit**

```bash
git add OTCamera/controller/upload_controller.py
git commit -m "feat: add UploadController subscribing to RecordingSplit events"
```

---

### Task 18: Status read model

**Files:**
- Rewrite: `OTCamera/status.py`
- Create: `tests/test_status.py`

**Step 1: Write the failing tests**

```python
# tests/test_status.py
from OTCamera.domain.events import (
    BatteryLow,
    EventBus,
    ExternalPowerConnected,
    ExternalPowerDisconnected,
    RecordingStarted,
    RecordingStopped,
    ShutdownRequested,
    WifiOff,
    WifiOn,
)
from OTCamera.status import Status


class TestStatus:
    def test_initial_state(self) -> None:
        bus = EventBus()
        status = Status(bus)
        assert status.is_recording is False
        assert status.wifi_on is True
        assert status.battery_low is False
        assert status.external_power_connected is False
        assert status.shutdown_active is False

    def test_recording_events(self) -> None:
        bus = EventBus()
        status = Status(bus)
        bus.emit(RecordingStarted(filename="test.h264"))
        assert status.is_recording is True
        bus.emit(RecordingStopped())
        assert status.is_recording is False

    def test_power_events(self) -> None:
        bus = EventBus()
        status = Status(bus)
        bus.emit(ExternalPowerConnected())
        assert status.external_power_connected is True
        bus.emit(ExternalPowerDisconnected())
        assert status.external_power_connected is False

    def test_battery_low(self) -> None:
        bus = EventBus()
        status = Status(bus)
        bus.emit(BatteryLow())
        assert status.battery_low is True

    def test_wifi_events(self) -> None:
        bus = EventBus()
        status = Status(bus)
        bus.emit(WifiOff())
        assert status.wifi_on is False
        bus.emit(WifiOn())
        assert status.wifi_on is True

    def test_shutdown_event(self) -> None:
        bus = EventBus()
        status = Status(bus)
        bus.emit(ShutdownRequested(source="button"))
        assert status.shutdown_active is True
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_status.py -v`
Expected: FAIL

**Step 3: Rewrite status.py**

```python
# OTCamera/status.py
"""Event-driven status read model.

Subscribes to events and accumulates current system state.
Read-only from outside — updated only by event handlers.
"""

from OTCamera.domain.events import (
    BatteryLow,
    EventBus,
    ExternalPowerConnected,
    ExternalPowerDisconnected,
    RecordingStarted,
    RecordingStopped,
    ShutdownRequested,
    WifiOff,
    WifiOn,
)


class Status:
    """Accumulates system state from events.

    Args:
        event_bus: Event bus to subscribe to.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._is_recording: bool = False
        self._wifi_on: bool = True
        self._battery_low: bool = False
        self._external_power_connected: bool = False
        self._shutdown_active: bool = False

        event_bus.subscribe(RecordingStarted, self._on_recording_started)
        event_bus.subscribe(RecordingStopped, self._on_recording_stopped)
        event_bus.subscribe(ExternalPowerConnected, self._on_ext_power_connected)
        event_bus.subscribe(ExternalPowerDisconnected, self._on_ext_power_disconnected)
        event_bus.subscribe(BatteryLow, self._on_battery_low)
        event_bus.subscribe(WifiOn, self._on_wifi_on)
        event_bus.subscribe(WifiOff, self._on_wifi_off)
        event_bus.subscribe(ShutdownRequested, self._on_shutdown)

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def wifi_on(self) -> bool:
        return self._wifi_on

    @property
    def battery_low(self) -> bool:
        return self._battery_low

    @property
    def external_power_connected(self) -> bool:
        return self._external_power_connected

    @property
    def shutdown_active(self) -> bool:
        return self._shutdown_active

    def _on_recording_started(self, event: RecordingStarted) -> None:
        self._is_recording = True

    def _on_recording_stopped(self, event: RecordingStopped) -> None:
        self._is_recording = False

    def _on_ext_power_connected(self, event: ExternalPowerConnected) -> None:
        self._external_power_connected = True

    def _on_ext_power_disconnected(self, event: ExternalPowerDisconnected) -> None:
        self._external_power_connected = False

    def _on_battery_low(self, event: BatteryLow) -> None:
        self._battery_low = True

    def _on_wifi_on(self, event: WifiOn) -> None:
        self._wifi_on = True

    def _on_wifi_off(self, event: WifiOff) -> None:
        self._wifi_on = False

    def _on_shutdown(self, event: ShutdownRequested) -> None:
        self._shutdown_active = True
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_status.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add OTCamera/status.py tests/test_status.py
git commit -m "refactor: rewrite Status as event-driven read model"
```

---

### Task 19: Rewrite __main__.py (wiring + main loop)

**Files:**
- Rewrite: `OTCamera/__main__.py`
- Modify: `OTCamera/record.py` (keep get_log_files_sorted, move OTCamera class logic)

**Step 1: Rewrite __main__.py**

```python
# OTCamera/__main__.py
"""OTCamera entry point.

Wires all components together and runs the main recording loop.
"""

import errno
import logging
import signal
import sys
from datetime import datetime as dt
from pathlib import Path
from time import sleep
from typing import Any, Dict, Iterator

from OTCamera.config import Config, parse_user_config
from OTCamera.controller.camera_controller import CameraController
from OTCamera.controller.power_controller import PowerController
from OTCamera.controller.schedule_controller import ScheduleController
from OTCamera.controller.upload_controller import UploadController
from OTCamera.controller.wifi_controller import WifiController
from OTCamera.domain.events import EventBus
from OTCamera.domain.led import LED
from OTCamera.helpers import log
from OTCamera.html_updater import (
    ConfigDataObject,
    ConfigHtmlId,
    LogDataObject,
    LogHtmlId,
    StatusWebsiteUpdater,
)
from OTCamera.plugin.adc.adc_provider import ADCProvider
from OTCamera.plugin.button.button_provider import ButtonProvider
from OTCamera.plugin.camera.camera_provider import CameraProvider
from OTCamera.plugin.led.led_provider import LEDProvider
from OTCamera.plugin.upload.upload_provider import UploadProvider
from OTCamera.status import Status

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
        status: Status,
        html_updater: StatusWebsiteUpdater,
        leds: Dict[str, LED],
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._camera = camera_controller
        self._power = power_controller
        self._wifi = wifi_controller
        self._schedule = schedule_controller
        self._status = status
        self._html_updater = html_updater
        self._leds = leds
        self._shutdown = False
        self._preview_taken = False
        self._power_led_blinked = False
        self._html_updated_after_recording = False

        signal.signal(signal.SIGTERM, self._execute_shutdown)

        Path(config.video.dir).mkdir(exist_ok=True)

    def record(self) -> None:
        """Run the main recording loop."""
        log.write("Starting periodic record")
        self._send_alive_signal()

        try:
            while self._camera.more_intervals:
                try:
                    self._loop()
                except OSError as oe:
                    if oe.errno == errno.ENOSPC:
                        log.write(str(oe), level=log.LogLevel.EXCEPTION)
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
        self._wifi.check_delayed_off()
        self._send_alive_signal()

        if self._schedule.should_record():
            self._camera.start_recording()
            self._camera.split_if_interval_ends()
            self._try_capture_preview()
            self._html_updated_after_recording = False
        else:
            self._camera.stop_recording()
            if not self._html_updated_after_recording:
                self._update_html()
                self._html_updated_after_recording = True
            sleep(0.5)

    def _send_alive_signal(self) -> None:
        """Blink power LED every 5 seconds as alive signal."""
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
        should_capture = is_preview_time and self._status.wifi_on and not self._preview_taken

        if should_capture and not self._status.shutdown_active:
            self._camera.capture()
            self._update_html()
            self._preview_taken = True
        elif not (is_preview_time or not self._preview_taken):
            self._preview_taken = False

    def _update_html(self) -> None:
        """Update the status website."""
        # TODO: Refactor html_updater to read from Status directly
        pass

    def _execute_shutdown(self, *args: Any) -> None:
        """Clean shutdown sequence."""
        if self._shutdown:
            return

        log.write("Stopping OTCamera", level=log.LogLevel.INFO)
        self._schedule.set_shutdown_active(True)
        self._camera.stop_recording()
        self._camera.close()
        log.write("OTCamera stopped", level=log.LogLevel.INFO)
        self._shutdown = True
        log.closefile()
        sys.exit(0)


def main(config_file: str = "~/user_config.yaml") -> None:
    """Wire up all components and start recording.

    Args:
        config_file: Path to YAML config file.
    """
    config = parse_user_config(config_file)
    event_bus = EventBus()

    # Plugins
    camera = CameraProvider.provide(config)
    adc = ADCProvider.provide(config)
    leds = LEDProvider.provide(config)
    buttons = ButtonProvider.provide(config, event_bus)

    upload = UploadProvider.provide(config)

    # Controllers
    camera_controller = CameraController(camera, config, event_bus, leds)
    power_controller = PowerController(config, event_bus, leds, adc)
    wifi_controller = WifiController(config, event_bus, leds)
    schedule_controller = ScheduleController(config, event_bus)
    upload_controller = UploadController(event_bus, upload)  # noqa: F841

    # Status read model
    status = Status(event_bus)

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

    # Init Wi-Fi from button state
    if config.buttons_enabled and "wifi" in buttons:
        wifi_controller.init_from_button(buttons["wifi"].is_pressed)

    # Run
    otcamera = OTCamera(
        config=config,
        event_bus=event_bus,
        camera_controller=camera_controller,
        power_controller=power_controller,
        wifi_controller=wifi_controller,
        schedule_controller=schedule_controller,
        status=status,
        html_updater=html_updater,
        leds=leds,
    )
    otcamera.record()


if __name__ == "__main__":
    main()
```

**Step 2: Update run.py to call new main()**

Update `run.py` to pass config_file to `OTCamera.__main__.main(config_file)` instead of the old `record.main()`.

**Step 3: Commit**

```bash
git add OTCamera/__main__.py run.py
git commit -m "refactor: rewrite __main__.py with new architecture wiring"
```

---

### Task 20: Cleanup — delete old files and directories

**Files to delete:**
- `OTCamera/hardware/` (entire directory)
- `OTCamera/plugin/camera/picamerax.py` (if not already deleted)
- `OTCamera/plugin_ftp_server/` (entire directory)
- `OTCamera/helpers/name.py` (absorbed into CameraController)
- `OTCamera/helpers/filesystem.py` (absorbed into CameraController)
- `OTCamera/helpers/rpi.py` (absorbed into PowerController)
- `OTCamera/helpers/errors.py` (NoMoreFilesToDeleteError no longer used)
- `OTCamera/record.py` (logic moved to __main__.py; keep `get_log_files_sorted` if needed by html_updater — move it there or into a utility)
- `OTCamera/domain/camera_errors.py` (if not already deleted)

**Step 1: Move get_log_files_sorted**

The `get_log_files_sorted` function from `record.py` is used by `OTCamera._get_log_info()`. If the html_updater still needs it, move it to `OTCamera/helpers/log.py` or keep it in `__main__.py`. Assess and place appropriately.

**Step 2: Delete old files**

```bash
rm -rf OTCamera/hardware/
rm -rf OTCamera/plugin_ftp_server/
rm -f OTCamera/helpers/name.py
rm -f OTCamera/helpers/filesystem.py
rm -f OTCamera/helpers/rpi.py
rm -f OTCamera/helpers/errors.py
rm -f OTCamera/record.py
rm -f OTCamera/domain/camera_errors.py
rm -f OTCamera/plugin/camera/picamerax.py
```

**Step 3: Remove empty __init__.py files if directories are empty**

Check `OTCamera/helpers/` — if only `log.py` and `__init__.py` remain, keep both.

**Step 4: Update any remaining imports across the codebase**

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
grep -r "import status" OTCamera/ tests/
grep -r "import config" OTCamera/ tests/
```

Fix all found references to point to new locations.

**Step 5: Run tests**

Run: `pytest -v`
Expected: All tests pass (some old tests may need updating — see Task 21)

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete old hardware/, helpers, plugin_ftp_server, record.py"
```

---

### Task 21: Update existing tests

**Files:**
- Modify: `tests/helpers/name_test.py` — functions moved into CameraController; tests need rewriting to test CameraController methods or be deleted
- Modify: `tests/helpers/filesystem_test.py` — functions absorbed into CameraController; adapt tests
- Modify: `tests/hardware/camera_test.py` — tests CameraProvider singleton; update import path
- Modify: `tests/record_test.py` — tests OTCamera class; update imports and constructor
- Modify: `tests/conftest.py` — if any fixtures reference old modules

**Step 1: Update or rewrite each test file**

For each test file, update imports to point to new locations. For tests that test absorbed functionality (name generation, filesystem), either:
- Rewrite as tests against CameraController (with a mock Camera)
- Keep as standalone utility tests if the functions are still accessible

**Step 2: Run all tests**

Run: `pytest -v`
Expected: all PASS

**Step 3: Run linting**

Run: `pre-commit run --all-files`
Fix any issues.

**Step 4: Commit**

```bash
git add -A
git commit -m "test: update tests for new architecture"
```

---

### Task 22: Final verification

**Step 1: Run full test suite**

```bash
pytest -v --tb=short
```

**Step 2: Run linting and type checking**

```bash
pre-commit run --all-files
mypy OTCamera tests --config-file=pyproject.toml
```

**Step 3: Verify directory structure matches design**

```bash
find OTCamera -type f -name "*.py" | sort
```

Expected structure should match the design doc.

**Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final cleanup and lint fixes"
```
