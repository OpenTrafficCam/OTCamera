# v2 Architecture Refactor — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor OTCamera into clean layers (domain / bsl / module / plugin / controller) with queue-based event bus, hardware ABCs, board support layer, and provider pattern for swappable components.

**Architecture:** Domain ABCs define contracts. BSL (Board Support Layer) implements board-specific hardware (LEDs, buttons, ADC) selected by PCB version via a single BoardProvider. Modules implement pluggable hardware (camera). Plugins handle swappable software components (upload). Controllers orchestrate logic against domain ABCs only. Hybrid EventBus provides synchronous `publish()` for main-thread controllers and thread-safe `enqueue()` for gpiozero callbacks, with `process_pending()` dispatching queued events once per loop iteration.

**Tech Stack:** Python >=3.11, gpiozero, picamera2, smbus2, psutil, pyyaml, beautifulsoup4, pytest

**Design doc:** `docs/plans/2026-03-05-v2-architecture-refactor-design.md`

---

### Task 1: Create branch and project scaffolding

**Files:**
- Create: `OTCamera/controller/__init__.py`
- Create: `OTCamera/bsl/__init__.py`
- Create: `OTCamera/bsl/boards/__init__.py`
- Create: `OTCamera/bsl/led/__init__.py`
- Create: `OTCamera/bsl/button/__init__.py`
- Create: `OTCamera/bsl/adc/__init__.py`
- Create: `OTCamera/module/__init__.py`
- Create: `OTCamera/module/camera/__init__.py`
- Create: `OTCamera/plugin/upload/__init__.py`

- [ ] **Step 1: Create empty package directories**

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
mkdir -p OTCamera/module/camera
touch OTCamera/module/__init__.py
touch OTCamera/module/camera/__init__.py
mkdir -p OTCamera/plugin/upload
touch OTCamera/plugin/upload/__init__.py
mkdir -p tests/domain tests/bsl tests/controller
touch tests/domain/__init__.py tests/bsl/__init__.py tests/controller/__init__.py
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "chore: scaffold new package directories for refactor"
```

---

### Task 2: Hybrid Event Bus (domain/events.py)

**Files:**
- Create: `OTCamera/domain/events.py`
- Create: `tests/domain/test_events.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/test_events.py
import threading

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


class TestPublish:
    def test_publish_dispatches_immediately(self) -> None:
        bus = EventBus()
        received: list[RecordingStarted] = []
        bus.subscribe(RecordingStarted, received.append)
        event = RecordingStarted(filename="/tmp/video.h264")
        bus.publish(event)
        assert received == [event]

    def test_publish_multiple_subscribers(self) -> None:
        bus = EventBus()
        results_a: list[BatteryLow] = []
        results_b: list[BatteryLow] = []
        bus.subscribe(BatteryLow, results_a.append)
        bus.subscribe(BatteryLow, results_b.append)
        bus.publish(BatteryLow())
        assert len(results_a) == 1
        assert len(results_b) == 1

    def test_publish_no_cross_talk(self) -> None:
        bus = EventBus()
        received: list[WifiOn] = []
        bus.subscribe(WifiOn, received.append)
        bus.publish(WifiOff())
        assert received == []

    def test_publish_exception_does_not_propagate(self) -> None:
        bus = EventBus()
        results: list[BatteryLow] = []

        def bad_callback(event: BatteryLow) -> None:
            raise RuntimeError("boom")

        bus.subscribe(BatteryLow, bad_callback)
        bus.subscribe(BatteryLow, results.append)
        bus.publish(BatteryLow())
        assert len(results) == 1


class TestEnqueue:
    def test_enqueue_does_not_dispatch_immediately(self) -> None:
        bus = EventBus()
        received: list[RecordingStarted] = []
        bus.subscribe(RecordingStarted, received.append)
        bus.enqueue(RecordingStarted(filename="/tmp/video.h264"))
        assert received == []

    def test_process_pending_dispatches_enqueued(self) -> None:
        bus = EventBus()
        received: list[RecordingStarted] = []
        bus.subscribe(RecordingStarted, received.append)
        event = RecordingStarted(filename="/tmp/video.h264")
        bus.enqueue(event)
        bus.process_pending()
        assert received == [event]

    def test_enqueue_is_thread_safe(self) -> None:
        bus = EventBus()
        received: list[ButtonPressed] = []
        bus.subscribe(ButtonPressed, received.append)

        def enqueue_from_thread() -> None:
            bus.enqueue(ButtonPressed(name="power"))

        t = threading.Thread(target=enqueue_from_thread)
        t.start()
        t.join()
        bus.process_pending()
        assert len(received) == 1
        assert received[0].name == "power"

    def test_process_pending_dispatches_all_queued(self) -> None:
        bus = EventBus()
        received: list[BatteryLow] = []
        bus.subscribe(BatteryLow, received.append)
        bus.enqueue(BatteryLow())
        bus.enqueue(BatteryLow())
        bus.enqueue(BatteryLow())
        bus.process_pending()
        assert len(received) == 3

    def test_process_pending_exception_does_not_propagate(self) -> None:
        bus = EventBus()
        results: list[BatteryLow] = []

        def bad_callback(event: BatteryLow) -> None:
            raise RuntimeError("boom")

        bus.subscribe(BatteryLow, bad_callback)
        bus.subscribe(BatteryLow, results.append)
        bus.enqueue(BatteryLow())
        bus.process_pending()
        assert len(results) == 1


class TestSubscriptionManagement:
    def test_unsubscribe(self) -> None:
        bus = EventBus()
        received: list[BatteryLow] = []
        bus.subscribe(BatteryLow, received.append)
        bus.unsubscribe(BatteryLow, received.append)
        bus.publish(BatteryLow())
        assert received == []

    def test_clear(self) -> None:
        bus = EventBus()
        received: list[BatteryLow] = []
        bus.subscribe(BatteryLow, received.append)
        bus.clear()
        bus.publish(BatteryLow())
        assert received == []


class TestEventDataclasses:
    def test_event_dataclass_fields(self) -> None:
        assert RecordingStarted(filename="vid.h264").filename == "vid.h264"
        assert RecordingSplit(filename="vid2.h264").filename == "vid2.h264"
        assert PreviewCaptured(path="/tmp/preview.jpg").path == "/tmp/preview.jpg"
        assert ShutdownRequested(source="battery").source == "battery"
        assert ButtonPressed(name="power").name == "power"
        assert ButtonHeld(name="wifi").name == "wifi"
        assert ButtonReleased(name="hour").name == "hour"

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
"""Hybrid event bus and event types for OTCamera.

Two dispatch paths:
- publish(event) dispatches synchronously to subscribers (main thread).
- enqueue(event) adds to a thread-safe queue (background threads).
- process_pending() dispatches all queued events on the calling thread.

Exceptions in callbacks are logged and swallowed — never crash the caller.
"""

import logging
import queue
from dataclasses import dataclass
from typing import Any, Callable

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
    """Reserved for future calendar-based scheduling."""

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
    """Hybrid in-process event bus with synchronous and queued dispatch.

    publish() dispatches synchronously — for main-thread controllers.
    enqueue() adds to a thread-safe queue — for background threads.
    process_pending() dispatches all queued events on the calling thread.
    """

    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[[Any], None]]] = {}
        self._queue: queue.Queue[Any] = queue.Queue()

    def subscribe(self, event_type: type, callback: Callable[[Any], None]) -> None:
        """Register a callback for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: type, callback: Callable[[Any], None]) -> None:
        """Remove a callback for an event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    def publish(self, event: Any) -> None:
        """Dispatch event synchronously to all subscribers.

        For main-thread use only. Exceptions are logged and swallowed.
        """
        self._dispatch(event)

    def enqueue(self, event: Any) -> None:
        """Enqueue an event for later dispatch. Thread-safe."""
        self._queue.put(event)

    def process_pending(self) -> None:
        """Dispatch all queued events on the calling thread."""
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                break
            self._dispatch(event)

    def clear(self) -> None:
        """Remove all subscribers and drain the queue."""
        self._subscribers.clear()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _dispatch(self, event: Any) -> None:
        """Dispatch event to subscribers. Log and swallow exceptions."""
        for callback in self._subscribers.get(type(event), []):
            try:
                callback(event)
            except Exception:
                logger.exception(
                    "Event callback %s failed for %s",
                    callback,
                    type(event).__name__,
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_events.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/domain/events.py tests/domain/test_events.py
git commit -m "feat: add hybrid event bus with publish/enqueue dispatch"
```

---

### Task 3: LED domain ABC

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

    def close(self) -> None:
        self._state = "closed"


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

    def test_close(self) -> None:
        led = FakeLED()
        led.close()
        assert led._state == "closed"

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
        raise NotImplementedError

    @abstractmethod
    def off(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def blink(
        self,
        on_time: float = 0.1,
        off_time: float = 0.1,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def pulse(
        self,
        fade_in_time: float = 0.25,
        fade_out_time: float = 0.25,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
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

### Task 4: Button domain ABC

**Files:**
- Create: `OTCamera/domain/button.py`
- Create: `tests/domain/test_button.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_button.py
import pytest

from OTCamera.domain.button import Button


class FakeButton(Button):
    def __init__(self) -> None:
        self._pressed = False
        self._on_pressed_cb: list = []
        self._on_held_cb: list = []
        self._on_released_cb: list = []

    def on_pressed(self, callback: object) -> None:
        self._on_pressed_cb.append(callback)

    def on_held(self, callback: object) -> None:
        self._on_held_cb.append(callback)

    def on_released(self, callback: object) -> None:
        self._on_released_cb.append(callback)

    @property
    def is_pressed(self) -> bool:
        return self._pressed

    def close(self) -> None:
        pass

    def simulate_press(self) -> None:
        self._pressed = True
        for cb in self._on_pressed_cb:
            cb()

    def simulate_hold(self) -> None:
        for cb in self._on_held_cb:
            cb()

    def simulate_release(self) -> None:
        self._pressed = False
        for cb in self._on_released_cb:
            cb()


class TestButtonABC:
    def test_on_pressed_callback(self) -> None:
        btn = FakeButton()
        results: list[str] = []
        btn.on_pressed(lambda: results.append("pressed"))
        btn.simulate_press()
        assert results == ["pressed"]

    def test_on_held_callback(self) -> None:
        btn = FakeButton()
        results: list[str] = []
        btn.on_held(lambda: results.append("held"))
        btn.simulate_hold()
        assert results == ["held"]

    def test_on_released_callback(self) -> None:
        btn = FakeButton()
        results: list[str] = []
        btn.on_released(lambda: results.append("released"))
        btn.simulate_release()
        assert results == ["released"]

    def test_is_pressed(self) -> None:
        btn = FakeButton()
        assert not btn.is_pressed
        btn.simulate_press()
        assert btn.is_pressed
        btn.simulate_release()
        assert not btn.is_pressed

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

Buttons provide hardware callbacks (on_pressed, on_held, on_released)
and an is_pressed property. Translation to event bus events happens
in __main__.py wiring, not in the button implementation.
"""

from abc import ABC, abstractmethod
from typing import Callable


class Button(ABC):

    @abstractmethod
    def on_pressed(self, callback: Callable[[], None]) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_held(self, callback: Callable[[], None]) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_released(self, callback: Callable[[], None]) -> None:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_pressed(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_button.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/domain/button.py tests/domain/test_button.py
git commit -m "feat: add Button abstract interface with callback pattern"
```

---

### Task 5: Upload domain ABC

**Files:**
- Create: `OTCamera/domain/upload.py`
- Create: `tests/domain/test_upload.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_upload.py
import pytest

from OTCamera.domain.upload import Upload, UploadError


class FakeUpload(Upload):
    def __init__(self, available: bool = True) -> None:
        self._available = available
        self.uploaded_files: list[str] = []

    def upload(self, file_path: str) -> None:
        self.uploaded_files.append(file_path)

    def is_available(self) -> bool:
        return self._available

    def close(self) -> None:
        pass


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

    def test_upload_error(self) -> None:
        err = UploadError("connection failed")
        assert str(err) == "connection failed"
        assert isinstance(err, Exception)
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


class UploadError(Exception):
    pass


class Upload(ABC):

    @abstractmethod
    def upload(self, file_path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    def close(self) -> None:
        """Close resources. Default no-op for implementations without resources."""
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_upload.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/domain/upload.py tests/domain/test_upload.py
git commit -m "feat: add Upload abstract interface with UploadError"
```

---

### Task 6: Merge CameraClosedError into camera.py, add ADCConfig and ADCTimeoutError

**Files:**
- Modify: `OTCamera/domain/camera.py`
- Modify: `OTCamera/domain/adc.py`
- Delete: `OTCamera/domain/camera_errors.py`
- Create: `tests/domain/test_adc.py`

- [ ] **Step 1: Write the failing test for ADCConfig**

```python
# tests/domain/test_adc.py
import pytest

from OTCamera.domain.adc import ADCConfig, ADCTimeoutError


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


class TestADCTimeoutError:
    def test_is_exception(self) -> None:
        err = ADCTimeoutError("I2C bus timeout")
        assert isinstance(err, Exception)
        assert str(err) == "I2C bus timeout"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_adc.py -v`
Expected: FAIL (cannot import ADCConfig)

- [ ] **Step 3: Add CameraClosedError to camera.py**

Add at the top of `OTCamera/domain/camera.py`, before the Camera class (after the imports and type literals):

```python
class CameraClosedError(Exception):
    pass
```

- [ ] **Step 4: Add `close()` to ADC ABC, add ADCConfig and ADCTimeoutError**

Add an abstract `close()` method to the existing `ADC` class, and append `ADCTimeoutError` and `ADCConfig` at the end of `OTCamera/domain/adc.py`:

```python
from dataclasses import dataclass


class ADCTimeoutError(Exception):
    pass


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

- [ ] **Step 5: Update import in hardware/camera_controller.py**

Change:
```python
from OTCamera.domain.camera_errors import CameraClosedError
```
To:
```python
from OTCamera.domain.camera import CameraClosedError
```

- [ ] **Step 6: Search for and update all other imports of camera_errors**

Run: `grep -r "camera_errors" OTCamera/ tests/`

Update all found imports to use `from OTCamera.domain.camera import CameraClosedError`.

- [ ] **Step 7: Delete camera_errors.py**

```bash
rm OTCamera/domain/camera_errors.py
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/domain/test_adc.py -v`
Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add OTCamera/domain/camera.py OTCamera/domain/adc.py tests/domain/test_adc.py
git add -u  # stage deleted camera_errors.py and updated imports
git commit -m "feat: add ADCConfig, ADCTimeoutError; merge CameraClosedError into camera.py"
```

---

### Task 7: Config dataclass

**Files:**
- Rewrite: `OTCamera/config.py`
- Create: `tests/test_config.py`

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
        server_upload:
          enable: true
          scheme: ftp
          host: example.com
          port: 21
          user: user
          password: pass
          server_source: /
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
        assert config.server_upload.enable is True

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        config = parse_user_config(str(tmp_path / "nonexistent.yaml"))
        assert config.camera.fps == 20
        assert config.debug_mode_on is False

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
        assert config.hardware.pcb_version == "v2"
        assert config.hardware.use_leds is False
        assert config.hardware.use_buttons is False
        assert config.hardware.use_adc is False
        assert config.server_upload.enable is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (imports not found)

- [ ] **Step 3: Rewrite config.py as dataclass**

```python
# OTCamera/config.py
"""OTCamera configuration.

Config is a nested dataclass loaded from YAML. parse_user_config()
reads YAML and returns a Config instance.
"""

import logging
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

try:
    from yaml import CSafeLoader as SafeLoader  # type: ignore[attr-defined]
except ImportError:
    from yaml import SafeLoader  # type: ignore[assignment]

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
    enable: bool = False
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
    pcb_version: str = "v2"
    use_leds: bool = False
    use_buttons: bool = False
    use_adc: bool = False


@dataclass
class MsTeamsConfig:
    enable: bool = False
    url: str | None = None
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


def _get(data: dict, key: str, default: object = None) -> object:  # type: ignore[type-arg]
    """Safely get a value from a dict."""
    try:
        return data[key]
    except KeyError:
        logger.debug("Missing config key: '%s', using default", key)
        return default


def parse_user_config(config_file: str) -> Config:
    """Parse YAML config file and return a Config instance."""
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
    r.start_hour = int(_get(section, "start_hour", r.start_hour))  # type: ignore[arg-type]
    r.end_hour = int(_get(section, "end_hour", r.end_hour))  # type: ignore[arg-type]
    r.interval_length = int(_get(section, "interval_length", r.interval_length))  # type: ignore[arg-type]
    r.num_intervals = int(_get(section, "num_intervals", r.num_intervals))  # type: ignore[arg-type]
    r.min_free_space = int(_get(section, "min_free_space", r.min_free_space))  # type: ignore[arg-type]

    # Camera
    section = data.get("camera", {})
    c = config.camera
    c.fps = int(_get(section, "fps", c.fps))  # type: ignore[arg-type]
    res = section.get("resolution", {})
    if res:
        c.resolution = (int(res.get("width", c.resolution[0])), int(res.get("height", c.resolution[1])))
    c.exposure_mode = str(_get(section, "exposure_mode", c.exposure_mode))
    c.drc_strength = str(_get(section, "drc_strength", c.drc_strength))
    c.rotation = int(_get(section, "rotation", c.rotation))  # type: ignore[arg-type]
    c.awb_mode = str(_get(section, "awb_mode", c.awb_mode))
    c.meter_mode = str(_get(section, "meter_mode", c.meter_mode))

    # Preview
    section = data.get("preview", {})
    p = config.preview
    p.path = str(_get(section, "path", p.path))
    p.format = str(_get(section, "format", p.format))
    p.interval = int(_get(section, "interval", p.interval))  # type: ignore[arg-type]
    p.send_to_external = bool(_get(section, "send_to_external", p.send_to_external))
    p.url = str(_get(section, "url", p.url))

    # Server upload
    section = data.get("server_upload", {})
    s = config.server_upload
    s.enable = bool(_get(section, "enable", s.enable))
    s.scheme = str(_get(section, "scheme", s.scheme))
    s.host = str(_get(section, "host", s.host))
    s.port = int(_get(section, "port", s.port))  # type: ignore[arg-type]
    s.user = str(_get(section, "user", s.user))
    s.password = str(_get(section, "password", s.password))
    s.server_source = str(_get(section, "server_source", s.server_source))

    # Video
    section = data.get("video", {})
    v = config.video
    v.dir = str(_get(section, "dir", v.dir))
    v.format = str(_get(section, "format", v.format))  # type: ignore[assignment]
    res = section.get("resolution", {})
    if res:
        v.resolution = (int(res.get("width", v.resolution[0])), int(res.get("height", v.resolution[1])))
    enc = section.get("encoder", {})
    if enc:
        v.h264_profile = str(_get(enc, "profile", v.h264_profile))  # type: ignore[assignment]
        v.h264_level = str(_get(enc, "level", v.h264_level))
        v.h264_bitrate = int(_get(enc, "bitrate", v.h264_bitrate))  # type: ignore[arg-type]
        v.h264_quality = int(_get(enc, "quality", v.h264_quality))  # type: ignore[arg-type]

    # Wifi
    section = data.get("wifi", {})
    config.wifi.delay = int(_get(section, "delay", config.wifi.delay))  # type: ignore[arg-type]

    # Hardware
    section = data.get("hardware", {})
    hw = config.hardware
    hw.pcb_version = str(_get(section, "pcb_version", hw.pcb_version))
    hw.use_leds = bool(_get(section, "use_leds", hw.use_leds))
    hw.use_buttons = bool(_get(section, "use_buttons", hw.use_buttons))
    hw.use_adc = bool(_get(section, "use_adc", hw.use_adc))

    # MS Teams
    section = data.get("msteams", {})
    config.msteams.enable = bool(_get(section, "enable", config.msteams.enable))
    config.msteams.url = _get(section, "url", config.msteams.url)  # type: ignore[assignment]
    config.msteams.max_failed_send_attempts = int(
        _get(section, "max_failed_send_attempts", config.msteams.max_failed_send_attempts)  # type: ignore[arg-type]
    )

    # ADC thresholds
    section = data.get("adc", {})
    config.adc.threshold_external_power = float(
        _get(section, "threshold_external_power", config.adc.threshold_external_power)  # type: ignore[arg-type]
    )
    config.adc.threshold_low_battery = float(
        _get(section, "threshold_low_battery", config.adc.threshold_low_battery)  # type: ignore[arg-type]
    )

    config.resolve_paths()
    return config
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/config.py tests/test_config.py
git commit -m "refactor: rewrite config as validated dataclass hierarchy"
```

---

### Task 8: Board Protocol and board definition

**Files:**
- Create: `OTCamera/bsl/boards/board.py`
- Create: `OTCamera/bsl/boards/v2.py`
- Create: `tests/bsl/test_board_definitions.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/bsl/test_board_definitions.py
import pytest

from OTCamera.bsl.boards.board import Board
from OTCamera.bsl.boards.v2 import BoardV2


class TestBoardDefinitions:
    def test_v2_satisfies_protocol(self) -> None:
        board: Board = BoardV2()
        assert board.led_power_pin >= 0
        assert board.adc_fsr > 0

    def test_v2_is_frozen(self) -> None:
        board = BoardV2()
        with pytest.raises(AttributeError):
            board.led_power_pin = 99  # type: ignore[misc]

    def test_v2_has_all_required_fields(self) -> None:
        required = [
            "led_power_pin", "led_wifi_pin", "led_rec_pin",
            "button_power_pin", "button_hour_pin", "button_wifi_pin",
            "button_power_pull_up", "button_hour_pull_up", "button_wifi_pull_up",
            "button_hold_time",
            "adc_i2c_address", "adc_fsr",
            "adc_channel_usb", "adc_channel_battery",
            "adc_divider_ratio_usb", "adc_divider_ratio_battery",
        ]
        board = BoardV2()
        for field_name in required:
            assert hasattr(board, field_name), f"BoardV2 missing {field_name}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bsl/test_board_definitions.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement Board Protocol**

```python
# OTCamera/bsl/boards/board.py
"""Board protocol — structural typing contract for board definitions.

All board definitions must provide these fields. Using Protocol (structural
subtyping) instead of ABC so frozen dataclasses can satisfy it without
inheritance.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Board(Protocol):
    """Contract for board definitions."""

    # LEDs (GPIO pin numbers)
    led_power_pin: int
    led_wifi_pin: int
    led_rec_pin: int

    # Buttons (GPIO pin numbers + config)
    button_power_pin: int
    button_hour_pin: int
    button_wifi_pin: int
    button_power_pull_up: bool
    button_hour_pull_up: bool
    button_wifi_pull_up: bool
    button_hold_time: float

    # ADC
    adc_i2c_address: int
    adc_fsr: float
    adc_channel_usb: int
    adc_channel_battery: int
    adc_divider_ratio_usb: float
    adc_divider_ratio_battery: float
```

- [ ] **Step 4: Implement BoardV2**

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

    # Buttons (GPIO pin numbers + config)
    button_power_pin: int = 21
    button_hour_pin: int = 20
    button_wifi_pin: int = 19
    button_power_pull_up: bool = True
    button_hour_pull_up: bool = True
    button_wifi_pull_up: bool = True
    button_hold_time: float = 2.0

    # ADC (TLA2024)
    adc_i2c_address: int = 0x48
    adc_fsr: float = 4.096
    adc_channel_usb: int = 0
    adc_channel_battery: int = 2
    adc_divider_ratio_usb: float = 2.0
    adc_divider_ratio_battery: float = 1510 / 510
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/bsl/test_board_definitions.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add OTCamera/bsl/boards/ tests/bsl/
git commit -m "feat: add Board protocol and v2 board definition"
```

---

### Task 9: BSL implementations (LED, Button, ADC)

**Files:**
- Create: `OTCamera/bsl/led/pwm_led.py`
- Create: `OTCamera/bsl/button/gpio_button.py`
- Create: `OTCamera/bsl/adc/tla2024.py`

No unit tests — these require Pi hardware.

- [ ] **Step 1: Implement PwmLed**

```python
# OTCamera/bsl/led/pwm_led.py
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

    def close(self) -> None:
        self._led.close()
```

- [ ] **Step 2: Implement GpioButton**

```python
# OTCamera/bsl/button/gpio_button.py
"""Button implementation using gpiozero."""

from typing import Callable

from gpiozero import Button as GpioZeroButton

from OTCamera.domain.button import Button


class GpioButton(Button):
    """Physical GPIO toggle switch.

    gpiozero mapping for toggle switches:
    - when_pressed  = switch flipped to ON
    - when_held     = switch stayed ON for hold_time seconds
    - when_released = switch flipped to OFF
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

    def on_pressed(self, callback: Callable[[], None]) -> None:
        self._button.when_pressed = callback

    def on_held(self, callback: Callable[[], None]) -> None:
        self._button.when_held = callback

    def on_released(self, callback: Callable[[], None]) -> None:
        self._button.when_released = callback

    @property
    def is_pressed(self) -> bool:
        return bool(self._button.is_pressed)

    def close(self) -> None:
        self._button.close()
```

- [ ] **Step 3: Copy TLA2024 to BSL**

Copy the existing `OTCamera/plugin/adc/tla2024.py` to `OTCamera/bsl/adc/tla2024.py`. Add `close()` method and `ADCTimeoutError` wrapping:

```python
# OTCamera/bsl/adc/tla2024.py
"""TLA2024 4-channel ADC implementation using I2C/smbus2."""

import logging
import time

import smbus2

from OTCamera.domain.adc import ADC, ADCTimeoutError

logger = logging.getLogger(__name__)

_MAX_POLL_ITERATIONS = 100


class TLA2024(ADC):
    """TLA2024 12-bit ADC with 4 single-ended input channels."""

    _REG_CONVERSION = 0x00
    _REG_CONFIG = 0x01
    _CONFIG_OS_SINGLE = 0x8000
    _CONFIG_MUX_OFFSET = 12
    _CONFIG_PGA_4_096V = 0x0200
    _CONFIG_MODE_SINGLE = 0x0100
    _CONFIG_DR_1600SPS = 0x0080
    _CONFIG_RESERVED = 0x0003

    _MUX_CHANNEL = {
        0: 0x4,
        1: 0x5,
        2: 0x6,
        3: 0x7,
    }

    def __init__(self, i2c_address: int = 0x48, fsr: float = 4.096) -> None:
        self._address = i2c_address
        self._fsr = fsr
        try:
            self._bus = smbus2.SMBus(1)
        except OSError as e:
            raise ADCTimeoutError(f"Failed to open I2C bus: {e}") from e

    @property
    def channels(self) -> int:
        return 4

    def get_voltage(self, channel: int) -> float:
        if channel not in self._MUX_CHANNEL:
            raise ValueError(f"Invalid channel {channel}. Must be 0-3.")

        config = (
            self._CONFIG_OS_SINGLE
            | (self._MUX_CHANNEL[channel] << self._CONFIG_MUX_OFFSET)
            | self._CONFIG_PGA_4_096V
            | self._CONFIG_MODE_SINGLE
            | self._CONFIG_DR_1600SPS
            | self._CONFIG_RESERVED
        )

        try:
            config_bytes = [(config >> 8) & 0xFF, config & 0xFF]
            self._bus.write_i2c_block_data(
                self._address, self._REG_CONFIG, config_bytes
            )

            for _ in range(_MAX_POLL_ITERATIONS):
                time.sleep(0.001)
                result = self._bus.read_i2c_block_data(
                    self._address, self._REG_CONFIG, 2
                )
                if result[0] & 0x80:
                    break
            else:
                raise ADCTimeoutError(
                    f"ADC conversion timeout on channel {channel}"
                )

            data = self._bus.read_i2c_block_data(
                self._address, self._REG_CONVERSION, 2
            )
        except OSError as e:
            raise ADCTimeoutError(f"I2C error on channel {channel}: {e}") from e

        raw_value = ((data[0] << 8) | data[1]) >> 4
        return (raw_value / 2048.0) * self._fsr

    def close(self) -> None:
        try:
            self._bus.close()
        except Exception:
            logger.debug("Error closing I2C bus", exc_info=True)
```

- [ ] **Step 4: Commit**

```bash
git add OTCamera/bsl/led/ OTCamera/bsl/button/ OTCamera/bsl/adc/
git commit -m "feat: add BSL implementations (PwmLed, GpioButton, TLA2024)"
```

---

### Task 10: BoardProvider

**Files:**
- Create: `OTCamera/bsl/board_provider.py`
- Create: `tests/bsl/test_board_provider.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/bsl/test_board_provider.py
import pytest

from OTCamera.bsl.board_provider import BoardComponents, load_board_definition
from OTCamera.bsl.boards.board import Board


class TestLoadBoardDefinition:
    def test_unknown_pcb_version_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown PCB version"):
            load_board_definition("v99")

    def test_v2_loads(self) -> None:
        board = load_board_definition("v2")
        assert isinstance(board, Board)
        assert board.led_power_pin >= 0

    def test_v2_has_correct_adc_address(self) -> None:
        board = load_board_definition("v2")
        assert board.adc_i2c_address == 0x48


class TestBoardComponents:
    def test_close_with_empty_dicts(self) -> None:
        bc = BoardComponents(leds={}, buttons={}, adc=None, adc_config=None)
        bc.close()  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bsl/test_board_provider.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement BoardProvider**

```python
# OTCamera/bsl/board_provider.py
"""Board provider — single entry point for all BSL components."""

import logging
from dataclasses import dataclass

from OTCamera.bsl.boards.board import Board
from OTCamera.bsl.boards.v2 import BoardV2
from OTCamera.config import Config
from OTCamera.domain.adc import ADC, ADCConfig
from OTCamera.domain.button import Button
from OTCamera.domain.led import LED

logger = logging.getLogger(__name__)

_BOARD_REGISTRY: dict[str, type] = {
    "v2": BoardV2,
}


@dataclass
class BoardComponents:
    """All hardware components provided by the board."""

    leds: dict[str, LED]
    buttons: dict[str, Button]
    adc: ADC | None
    adc_config: ADCConfig | None

    def close(self) -> None:
        """Close all components. Exception-safe: log and continue."""
        for name, led in self.leds.items():
            try:
                led.close()
            except Exception:
                logger.exception("Failed to close LED %s", name)
        for name, button in self.buttons.items():
            try:
                button.close()
            except Exception:
                logger.exception("Failed to close button %s", name)
        if self.adc is not None:
            try:
                self.adc.close()
            except Exception:
                logger.exception("Failed to close ADC")


def load_board_definition(pcb_version: str) -> Board:
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
    def provide(config: Config) -> BoardComponents:
        board = load_board_definition(config.hardware.pcb_version)
        logger.info("Loaded board definition: PCB %s", config.hardware.pcb_version)

        leds: dict[str, LED] = {}
        buttons: dict[str, Button] = {}
        adc: ADC | None = None
        adc_config: ADCConfig | None = None
        created_components: list = []

        try:
            if config.hardware.use_leds or config.hardware.use_buttons:
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
                created_components.extend(leds.values())
                for led in leds.values():
                    led.off()
                logger.debug("LEDs initialized: %s", list(leds.keys()))

            if config.hardware.use_buttons:
                from OTCamera.bsl.button.gpio_button import GpioButton

                buttons = {
                    "power": GpioButton(
                        board.button_power_pin,
                        pull_up=board.button_power_pull_up,
                        hold_time=board.button_hold_time,
                    ),
                    "hour": GpioButton(
                        board.button_hour_pin,
                        pull_up=board.button_hour_pull_up,
                        hold_time=board.button_hold_time,
                    ),
                    "wifi": GpioButton(
                        board.button_wifi_pin,
                        pull_up=board.button_wifi_pull_up,
                        hold_time=board.button_hold_time,
                    ),
                }
                created_components.extend(buttons.values())
                logger.debug("Buttons initialized: %s", list(buttons.keys()))

            if config.hardware.use_adc:
                from OTCamera.bsl.adc.tla2024 import TLA2024

                adc = TLA2024(board.adc_i2c_address, board.adc_fsr)
                created_components.append(adc)
                adc_config = ADCConfig(
                    channel_usb=board.adc_channel_usb,
                    channel_battery=board.adc_channel_battery,
                    divider_ratio_usb=board.adc_divider_ratio_usb,
                    divider_ratio_battery=board.adc_divider_ratio_battery,
                )
                logger.debug("ADC initialized")

        except Exception:
            # Close already-created components before propagating
            for comp in created_components:
                try:
                    comp.close()
                except Exception:
                    logger.exception("Failed to close component during init cleanup")
            raise

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

### Task 11: Camera module (drop picamerax, update provider)

**Files:**
- Create: `OTCamera/module/camera/camera_provider.py`
- Create: `OTCamera/module/camera/picamera2.py` (copy from plugin, decouple from config)
- Delete: `OTCamera/plugin/camera/picamerax.py`

- [ ] **Step 1: Create new CameraProvider**

```python
# OTCamera/module/camera/camera_provider.py
"""Provider that creates camera backend based on config."""

import logging

from OTCamera.config import Config
from OTCamera.domain.camera import Camera

logger = logging.getLogger(__name__)


class CameraProvider:
    """Creates a Camera instance based on config."""

    @staticmethod
    def provide(config: Config) -> Camera:
        from picamera2 import Picamera2

        from OTCamera.module.camera.picamera2 import PiCamera2, load_tuning_with_drc

        c = config.camera
        tuning = load_tuning_with_drc(c.drc_strength)
        try:
            picam2 = Picamera2(tuning=tuning)
        except IndexError:
            raise RuntimeError(
                "No camera detected by libcamera. "
                "Check that the camera is connected and the interface is enabled."
            ) from None
        camera = PiCamera2(
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
        return camera
```

- [ ] **Step 2: Copy and decouple picamera2.py**

Copy `OTCamera/plugin/camera/picamera2.py` to `OTCamera/module/camera/picamera2.py`.

Apply these changes:
- Remove `from OTCamera import config` import
- Remove all `config.*` default parameter values from `__init__` — all values are passed explicitly by `CameraProvider`
- Replace `from OTCamera.helpers import log` with `import logging` and use `logger = logging.getLogger(__name__)`
- Replace all `log.write(msg, level=log.LogLevel.X)` calls with `logger.x(msg)`
- Store `start_recording()` parameters as instance variables for `split_recording()` fallback
- Fix: pass `h264_level` to `H264Encoder(bitrate=bitrate, profile=h264_profile, level=h264_level)` — currently silently ignored

- [ ] **Step 3: Delete picamerax**

```bash
rm OTCamera/plugin/camera/picamerax.py
```

- [ ] **Step 4: Commit**

```bash
git add OTCamera/module/camera/
git add -u
git commit -m "feat: add camera module with decoupled picamera2 provider"
```

---

### Task 12: Upload plugin (FTP)

**Files:**
- Create: `OTCamera/plugin/upload/ftp_upload.py`
- Create: `OTCamera/plugin/upload/upload_provider.py`

- [ ] **Step 1: Implement FtpUpload**

```python
# OTCamera/plugin/upload/ftp_upload.py
"""Upload implementation using FTPS."""

import logging
from ftplib import FTP_TLS
from pathlib import Path

from OTCamera.domain.upload import Upload, UploadError

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
        source = Path(file_path)
        dest = Path(self._server_source) / source.name

        logger.debug(
            "File to upload: %s (size: %d bytes)", source, source.stat().st_size
        )

        client = self._connect()
        try:
            self._navigate_to_dir(client, dest.parent)
            with open(source, "rb") as f:
                client.storbinary(f"STOR {dest.name}", f)
            logger.info("Uploaded %s", source.name)
        except Exception as e:
            raise UploadError(f"Upload failed for {source.name}: {e}") from e
        finally:
            client.close()

    def is_available(self) -> bool:
        try:
            client = self._connect()
            client.close()
            return True
        except Exception:
            return False

    def _connect(self) -> FTP_TLS:
        ftp = FTP_TLS()
        ftp.connect(self._host, self._port, timeout=30)
        ftp.login(self._user, self._password)
        ftp.prot_p()
        return ftp

    def _navigate_to_dir(self, client: FTP_TLS, path: Path) -> None:
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
# OTCamera/plugin/upload/upload_provider.py
"""Provider that creates upload backend based on config."""

import logging

from OTCamera.config import Config
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadProvider:
    """Creates an Upload instance based on config, or None if disabled."""

    @staticmethod
    def provide(config: Config) -> Upload | None:
        if not config.server_upload.enable:
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

- [ ] **Step 3: Commit**

```bash
git add OTCamera/plugin/upload/
git commit -m "feat: add Upload plugin with FTP and UploadProvider"
```

---

### Task 13: ScheduleController

**Files:**
- Create: `OTCamera/controller/schedule_controller.py`
- Create: `tests/controller/test_schedule_controller.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/controller/test_schedule_controller.py
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

    def test_overnight_window(self) -> None:
        config = Config()
        config.recording.start_hour = 22
        config.recording.end_hour = 6
        bus = EventBus()
        sc = ScheduleController(config, bus)
        with patch.object(sc, "_current_hour", return_value=23):
            assert sc.should_record() is True
        with patch.object(sc, "_current_hour", return_value=3):
            assert sc.should_record() is True
        with patch.object(sc, "_current_hour", return_value=12):
            assert sc.should_record() is False

    def test_hour_switch_on_enables_24_7(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)
        bus.enqueue(ButtonPressed(name="hour"))
        bus.process_pending()
        with patch.object(sc, "_current_hour", return_value=23):
            assert sc.should_record() is True

    def test_hour_switch_off_restores_schedule(self) -> None:
        config = Config()
        config.recording.start_hour = 6
        config.recording.end_hour = 22
        bus = EventBus()
        sc = ScheduleController(config, bus)
        bus.enqueue(ButtonPressed(name="hour"))
        bus.enqueue(ButtonReleased(name="hour"))
        bus.process_pending()
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
        bus.enqueue(ButtonPressed(name="wifi"))
        bus.process_pending()
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
time windows and hour switch overrides.
"""

import logging
from datetime import datetime as dt

from OTCamera.config import Config
from OTCamera.domain.events import ButtonPressed, ButtonReleased, EventBus

logger = logging.getLogger(__name__)


class ScheduleController:
    """Determines if recording should be active."""

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
        if self._shutdown_active:
            return False
        if self._24_7_mode:
            return True
        hour = self._current_hour()
        start = self._config.recording.start_hour
        end = self._config.recording.end_hour
        if start < end:
            return start <= hour < end
        else:
            # Overnight window (e.g., start=22, end=6)
            return hour >= start or hour < end

    def init_from_switch(self, hour_switch_on: bool) -> None:
        self._24_7_mode = hour_switch_on
        if hour_switch_on:
            logger.info("Hour switch ON at boot — 24/7 mode enabled")

    def set_shutdown_active(self, active: bool) -> None:
        self._shutdown_active = active

    def _current_hour(self) -> int:
        return dt.now().hour

    def _on_switch_pressed(self, event: ButtonPressed) -> None:
        if event.name != "hour":
            return
        self._24_7_mode = True
        logger.info("Hour switch ON — 24/7 mode enabled")

    def _on_switch_released(self, event: ButtonReleased) -> None:
        if event.name != "hour":
            return
        self._24_7_mode = False
        logger.info("Hour switch OFF — scheduled mode restored")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/controller/test_schedule_controller.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add OTCamera/controller/schedule_controller.py tests/controller/test_schedule_controller.py
git commit -m "feat: add ScheduleController with overnight window support"
```

---

### Task 14: PowerController

**Files:**
- Create: `OTCamera/controller/power_controller.py`

- [ ] **Step 1: Implement PowerController**

```python
# OTCamera/controller/power_controller.py
"""Power monitoring and system control.

Monitors battery/USB via ADC, emits power events, handles system shutdown.
Power switch OFF starts a countdown. Switch back ON cancels it.
Same behavior at boot via init_from_switch().
"""

import logging
from datetime import datetime as dt
from datetime import timedelta
from subprocess import call
from typing import Any

from OTCamera.config import Config
from OTCamera.domain.adc import ADC, ADCConfig, ADCTimeoutError
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
    """Monitors power status via ADC and handles shutdown."""

    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        leds: dict[str, LED],
        adc: ADC | None = None,
        adc_config: ADCConfig | None = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._adc = adc
        self._adc_config = adc_config
        self._external_power_connected = False
        self._battery_is_low = False
        self._power_off_time: dt | None = None

        event_bus.subscribe(ButtonPressed, self._on_button_pressed)
        event_bus.subscribe(ButtonReleased, self._on_button_released)

        if adc and adc_config:
            try:
                self._external_power_connected = self.is_external_power
            except ADCTimeoutError:
                logger.warning("ADC timeout during init, assuming no external power")

    @property
    def has_adc(self) -> bool:
        return self._adc is not None

    @property
    def is_low_battery(self) -> bool:
        if not self._adc or not self._adc_config:
            return False
        try:
            voltage = self._adc.get_voltage(self._adc_config.channel_battery)
            return (
                voltage * self._adc_config.divider_ratio_battery
                < self._config.adc.threshold_low_battery
            )
        except ADCTimeoutError:
            logger.warning("ADC timeout reading battery, assuming OK")
            return False

    @property
    def battery_is_low(self) -> bool:
        return self._battery_is_low

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
        return self._power_off_time is not None

    def check_power_status(self) -> None:
        """Check power status and emit events. Called from main loop."""
        if not self._adc or not self._adc_config:
            return

        if self.is_low_battery and not self._battery_is_low:
            self._on_low_battery()

        was_connected = self._external_power_connected
        try:
            is_connected = self.is_external_power
        except ADCTimeoutError:
            logger.warning("ADC timeout reading USB, keeping previous state")
            return

        if is_connected and not was_connected:
            self._external_power_connected = True
            logger.info("External power connected")
            self._event_bus.publish(ExternalPowerConnected())
        elif not is_connected and was_connected:
            self._external_power_connected = False
            logger.warning("External power disconnected")
            self._event_bus.publish(ExternalPowerDisconnected())

    def check_pending_shutdown(self) -> None:
        """Check if shutdown countdown has elapsed. Called from main loop."""
        if self._power_off_time is None:
            return
        if self._power_off_time + timedelta(seconds=_POWER_SHUTDOWN_DELAY) < dt.now():
            self._power_off_time = None
            self.shutdown(source="button")

    def shutdown(self, source: str = "unknown") -> None:
        """Publish ShutdownRequested (triggers cleanup synchronously), then OS shutdown."""
        logger.info("Shutdown requested by %s", source)
        self._event_bus.publish(ShutdownRequested(source=source))

        power_led = self._leds.get("power")
        if power_led:
            power_led.on()

        if self._config.use_relay:
            call(["sudo", "systemctl", "stop", "sshrelay.service"])
            logger.info("Stopped SSH relay")

        if not self._config.debug_mode_on:
            call(["sudo", "shutdown", "-h", "now"])

    def reboot(self) -> None:
        logger.info("Rebooting")
        power_led = self._leds.get("power")
        if power_led:
            power_led.blink(on_time=0.1, off_time=0.1, n=None, background=True)

        if self._config.use_relay:
            call(["sudo", "systemctl", "stop", "sshrelay.service"])

        if not self._config.debug_mode_on:
            call(["sudo", "reboot"])

    def _on_button_pressed(self, event: ButtonPressed) -> None:
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
        if event.name != "power":
            return
        self._power_off_time = dt.now()
        logger.info("Power switch OFF — shutdown in %ds", _POWER_SHUTDOWN_DELAY)
        power_led = self._leds.get("power")
        if power_led:
            power_led.blink(on_time=0.1, off_time=0.4, n=None, background=True)

    def _on_low_battery(self) -> None:
        self._battery_is_low = True
        logger.warning("Battery level is low!")
        self._event_bus.publish(BatteryLow())
        self.shutdown(source="battery")
```

- [ ] **Step 2: Write PowerController tests**

```python
# tests/controller/test_power_controller.py
from datetime import datetime as dt
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from OTCamera.config import Config
from OTCamera.controller.power_controller import PowerController, _POWER_SHUTDOWN_DELAY
from OTCamera.domain.adc import ADC, ADCConfig, ADCTimeoutError
from OTCamera.domain.events import (
    BatteryLow,
    ButtonPressed,
    ButtonReleased,
    EventBus,
    ExternalPowerConnected,
    ExternalPowerDisconnected,
    ShutdownRequested,
)


class FakeADC(ADC):
    def __init__(self) -> None:
        self.voltages: dict[int, float] = {0: 0.0, 2: 0.0}

    @property
    def channels(self) -> int:
        return 4

    def get_voltage(self, channel: int) -> float:
        return self.voltages.get(channel, 0.0)

    def close(self) -> None:
        pass


@pytest.fixture
def adc_config() -> ADCConfig:
    return ADCConfig(
        channel_usb=0,
        channel_battery=2,
        divider_ratio_usb=2.0,
        divider_ratio_battery=3.0,
    )


@pytest.fixture
def config() -> Config:
    c = Config()
    c.adc.threshold_external_power = 2.5
    c.adc.threshold_low_battery = 3.3
    c.debug_mode_on = True  # prevent actual shutdown
    return c


class TestPowerControllerNoADC:
    def test_no_adc_defaults(self) -> None:
        bus = EventBus()
        pc = PowerController(Config(), bus, {})
        assert not pc.has_adc
        assert not pc.is_low_battery
        assert not pc.is_external_power

    def test_check_power_status_no_adc(self) -> None:
        bus = EventBus()
        pc = PowerController(Config(), bus, {})
        pc.check_power_status()  # should not raise


class TestPowerControllerWithADC:
    def test_external_power_detected(
        self, config: Config, adc_config: ADCConfig
    ) -> None:
        adc = FakeADC()
        adc.voltages[0] = 2.0  # 2.0 * 2.0 = 4.0 > 2.5
        bus = EventBus()
        pc = PowerController(config, bus, {}, adc, adc_config)
        assert pc.is_external_power

    def test_low_battery_detected(
        self, config: Config, adc_config: ADCConfig
    ) -> None:
        adc = FakeADC()
        adc.voltages[2] = 1.0  # 1.0 * 3.0 = 3.0 < 3.3
        bus = EventBus()
        pc = PowerController(config, bus, {}, adc, adc_config)
        assert pc.is_low_battery

    def test_battery_ok(self, config: Config, adc_config: ADCConfig) -> None:
        adc = FakeADC()
        adc.voltages[2] = 1.5  # 1.5 * 3.0 = 4.5 > 3.3
        bus = EventBus()
        pc = PowerController(config, bus, {}, adc, adc_config)
        assert not pc.is_low_battery

    def test_external_power_event_emitted(
        self, config: Config, adc_config: ADCConfig
    ) -> None:
        adc = FakeADC()
        adc.voltages[0] = 0.0  # no external power initially
        bus = EventBus()
        pc = PowerController(config, bus, {}, adc, adc_config)
        received: list = []
        bus.subscribe(ExternalPowerConnected, received.append)
        adc.voltages[0] = 2.0  # now external power
        pc.check_power_status()
        bus.process_pending()
        assert len(received) == 1

    def test_adc_timeout_battery_assumes_ok(
        self, config: Config, adc_config: ADCConfig
    ) -> None:
        adc = MagicMock(spec=ADC)
        adc.get_voltage.side_effect = ADCTimeoutError("timeout")
        bus = EventBus()
        pc = PowerController(config, bus, {}, adc, adc_config)
        assert not pc.is_low_battery  # assumes OK on timeout


class TestPowerButtonCountdown:
    def test_button_released_starts_countdown(self) -> None:
        bus = EventBus()
        pc = PowerController(Config(debug_mode_on=True), bus, {})
        bus.enqueue(ButtonReleased(name="power"))
        bus.process_pending()
        assert pc.shutdown_active

    def test_button_pressed_cancels_countdown(self) -> None:
        bus = EventBus()
        pc = PowerController(Config(debug_mode_on=True), bus, {})
        bus.enqueue(ButtonReleased(name="power"))
        bus.enqueue(ButtonPressed(name="power"))
        bus.process_pending()
        assert not pc.shutdown_active

    def test_countdown_expires_triggers_shutdown(self) -> None:
        bus = EventBus()
        received: list = []
        bus.subscribe(ShutdownRequested, received.append)
        pc = PowerController(Config(debug_mode_on=True), bus, {})
        bus.enqueue(ButtonReleased(name="power"))
        bus.process_pending()
        # Simulate time passing
        pc._power_off_time = dt.now() - timedelta(seconds=_POWER_SHUTDOWN_DELAY + 1)
        pc.check_pending_shutdown()
        bus.process_pending()
        assert len(received) == 1
        assert received[0].source == "button"


    def test_other_button_ignored(self) -> None:
        bus = EventBus()
        pc = PowerController(Config(debug_mode_on=True), bus, {})
        bus.enqueue(ButtonReleased(name="wifi"))
        bus.process_pending()
        assert not pc.shutdown_active
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/controller/test_power_controller.py -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add OTCamera/controller/power_controller.py tests/controller/test_power_controller.py
git commit -m "feat: add PowerController with ADC monitoring and shutdown countdown"
```

---

### Task 15: WifiController

**Files:**
- Create: `OTCamera/controller/wifi_controller.py`

- [ ] **Step 1: Implement WifiController**

```python
# OTCamera/controller/wifi_controller.py
"""Wi-Fi control via button events."""

import logging
import re
import subprocess
from datetime import datetime as dt
from datetime import timedelta

from OTCamera.config import Config
from OTCamera.domain.events import (
    ButtonHeld,
    ButtonPressed,
    ButtonReleased,
    EventBus,
    WifiOff,
    WifiOn,
)
from OTCamera.domain.led import LED

logger = logging.getLogger(__name__)


class WifiController:
    """Manages Wi-Fi AP state based on wifi switch events."""

    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        leds: dict[str, LED],
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._wifi_on: bool = True
        self._switch_off_time: dt | None = None

        event_bus.subscribe(ButtonHeld, self._on_switch_held)
        event_bus.subscribe(ButtonPressed, self._on_switch_pressed)
        event_bus.subscribe(ButtonReleased, self._on_switch_released)

    @property
    def wifi_on(self) -> bool:
        return self._wifi_on

    @property
    def switch_off_time(self) -> dt | None:
        return self._switch_off_time

    def init_from_switch(self, wifi_switch_on: bool) -> None:
        if wifi_switch_on:
            self.switch_on()
        else:
            self.switch_off()

    def switch_on(self) -> None:
        self._switch_off_time = None
        if not self._wifi_on:
            if not self._config.debug_mode_on:
                subprocess.call(["sudo", "rfkill", "unblock", "wlan"])
            if self._config.use_relay:
                subprocess.call(["sudo", "systemctl", "start", "sshrelay.service"])
                logger.info("Started SSH relay")
            self._wifi_on = True
            logger.info("Wi-Fi on")
            self._event_bus.publish(WifiOn())

        wifi_led = self._leds.get("wifi")
        if wifi_led:
            wifi_led.blink(on_time=0.1, off_time=4.9, n=None, background=True)

    def switch_off(self) -> None:
        if self._wifi_on:
            if not self._config.debug_mode_on:
                subprocess.call(["sudo", "rfkill", "block", "wlan"])
            if self._config.use_relay:
                subprocess.call(["sudo", "systemctl", "stop", "sshrelay.service"])
                logger.info("Stopped SSH relay")
            self._wifi_on = False
            logger.info("Wi-Fi off")
            self._event_bus.publish(WifiOff())

        wifi_led = self._leds.get("wifi")
        if wifi_led:
            wifi_led.pulse(
                fade_in_time=0.25, fade_out_time=0.25, n=4, background=True
            )

    def check_pending_wifi_off(self) -> None:
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
        if event.name != "wifi":
            return
        self.switch_on()

    def _on_switch_pressed(self, event: ButtonPressed) -> None:
        if event.name != "wifi":
            return
        self.switch_on()

    def _on_switch_released(self, event: ButtonReleased) -> None:
        if event.name != "wifi":
            return
        self._switch_off_time = dt.now()
        wifi_led = self._leds.get("wifi")
        if wifi_led:
            wifi_led.blink(on_time=0.1, off_time=0.9, n=None, background=True)
        logger.info("Wi-Fi turning off in %d s", self._config.wifi.delay)

    @staticmethod
    def is_wifi_enabled(device: str = "wlan0") -> bool:
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

- [ ] **Step 2: Write WifiController tests**

```python
# tests/controller/test_wifi_controller.py
from datetime import datetime as dt
from datetime import timedelta
from unittest.mock import patch

import pytest

from OTCamera.config import Config
from OTCamera.controller.wifi_controller import WifiController
from OTCamera.domain.events import (
    ButtonHeld,
    ButtonPressed,
    ButtonReleased,
    EventBus,
    WifiOff,
    WifiOn,
)


@pytest.fixture
def config() -> Config:
    c = Config()
    c.wifi.delay = 10
    c.debug_mode_on = True  # prevent actual rfkill calls
    return c


class TestWifiControllerSwitchOn:
    def test_switch_pressed_turns_wifi_on(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        wc._wifi_on = False
        bus.enqueue(ButtonPressed(name="wifi"))
        bus.process_pending()
        assert wc.wifi_on

    def test_switch_pressed_cancels_delayed_off(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        wc._switch_off_time = dt.now()
        bus.enqueue(ButtonPressed(name="wifi"))
        bus.process_pending()
        assert wc.switch_off_time is None

    def test_switch_held_turns_wifi_on(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        wc._wifi_on = False
        bus.enqueue(ButtonHeld(name="wifi"))
        bus.process_pending()
        assert wc.wifi_on

    def test_wifi_on_event_emitted(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        wc._wifi_on = False
        received: list = []
        bus.subscribe(WifiOn, received.append)
        bus.enqueue(ButtonPressed(name="wifi"))
        bus.process_pending()  # dispatches ButtonPressed → switch_on → publishes WifiOn
        assert len(received) == 1


class TestWifiControllerSwitchOff:
    def test_switch_released_starts_delay(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        bus.enqueue(ButtonReleased(name="wifi"))
        bus.process_pending()
        assert wc.switch_off_time is not None

    def test_delayed_off_turns_wifi_off(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        wc._switch_off_time = dt.now() - timedelta(seconds=config.wifi.delay + 1)
        wc.check_pending_wifi_off()
        assert not wc.wifi_on

    def test_delayed_off_not_expired(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        wc._switch_off_time = dt.now()
        wc.check_pending_wifi_off()
        assert wc.wifi_on

    def test_wifi_off_event_emitted(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        received: list = []
        bus.subscribe(WifiOff, received.append)
        wc._switch_off_time = dt.now() - timedelta(seconds=config.wifi.delay + 1)
        wc.check_pending_wifi_off()
        bus.process_pending()
        assert len(received) == 1


class TestWifiControllerInitFromSwitch:
    def test_init_from_switch_on(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        wc._wifi_on = False
        wc.init_from_switch(True)
        assert wc.wifi_on

    def test_init_from_switch_off(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        wc.init_from_switch(False)
        assert not wc.wifi_on


class TestWifiControllerOtherButtons:
    def test_other_button_pressed_ignored(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        wc._wifi_on = False
        bus.enqueue(ButtonPressed(name="power"))
        bus.process_pending()
        assert not wc.wifi_on

    def test_other_button_released_ignored(self, config: Config) -> None:
        bus = EventBus()
        wc = WifiController(config, bus, {})
        bus.enqueue(ButtonReleased(name="hour"))
        bus.process_pending()
        assert wc.switch_off_time is None
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/controller/test_wifi_controller.py -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add OTCamera/controller/wifi_controller.py tests/controller/test_wifi_controller.py
git commit -m "feat: add WifiController with delayed off timer"
```

---

### Task 16: CameraController

**Files:**
- Create: `OTCamera/controller/camera_controller.py`

- [ ] **Step 1: Implement CameraController**

```python
# OTCamera/controller/camera_controller.py
"""Camera recording orchestration.

Handles start/stop/split recording, preview capture, disk space management,
and annotation text. Emits events for non-critical subscribers.
"""

import base64
import logging
from datetime import datetime as dt
from pathlib import Path
from time import sleep

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
    """Orchestrates camera recording lifecycle."""

    def __init__(
        self,
        camera: Camera,
        config: Config,
        event_bus: EventBus,
        leds: dict[str, LED],
    ) -> None:
        self._camera = camera
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._current_video_file: str = self._video_filename()
        self._last_split_minute: int = -1
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
        self._last_split_minute = dt.now().minute  # prevent immediate split
        logger.info("Started recording: %s", self._current_video_file)
        self._led_recording_on()
        self._event_bus.publish(RecordingStarted(filename=self._current_video_file))
        self._wait_recording(2)
        self.capture()

    def stop_recording(self) -> None:
        if self._camera.is_recording:
            self._camera.stop_recording()
            self._led_recording_off()
            logger.info("Stopped recording. Videos: %d", self._current_interval)
            self._event_bus.publish(RecordingStopped())

    def split_if_interval_ends(self) -> None:
        current_minute = dt.now().minute
        interval = self._config.recording.interval_length

        if (current_minute % interval == 0) and (current_minute != self._last_split_minute):
            self._last_split_minute = current_minute
            self._split()
            self._current_interval += 1
            num = self._config.recording.num_intervals
            if num > 0:
                self._more_intervals = self._current_interval < num
            if not self._more_intervals:
                logger.debug("Last interval reached")

        self._wait_recording(0.5)
        self._set_annotation_text()

    def capture(self) -> None:
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
        self._event_bus.publish(PreviewCaptured(path=preview_path))

    def close(self) -> None:
        try:
            self._camera.close()
            logger.debug("Camera closed")
        except CameraClosedError:
            logger.debug("Camera already closed")

    def restart(self) -> None:
        logger.info("Restarting camera")
        self._camera.reinitialize()

    # --- Filename generation ---

    def _video_filename(self) -> str:
        c = self._config
        filename = (
            Path(c.video.dir)
            / f"{c.prefix}_FR{c.camera.fps}_{self._current_dt()}.{c.video.format}"
        )
        return str(filename.expanduser().resolve())

    def _preview_path(self) -> str:
        return str(Path(self._config.preview.path).expanduser().resolve())

    def _annotate_text(self) -> str:
        return dt.now().strftime(self._config.prefix + " %d.%m.%Y %H:%M:%S")

    @staticmethod
    def _current_dt() -> str:
        return dt.now().strftime("%Y-%m-%d_%H-%M-%S")

    def _set_annotation_text(self) -> None:
        self._camera.set_annotation_text(self._annotate_text())

    # --- Disk space management ---

    def delete_old_files(self) -> None:
        video_dir = Path(self._config.video.dir).expanduser().resolve()
        min_bytes = self._config.recording.min_free_space * 1024 * 1024 * 1024
        logger.debug("Checking disk space")

        current = Path(self._current_video_file) if self._camera.is_recording else None

        while psutil.disk_usage(str(video_dir)).free <= min_bytes:
            video_paths = [
                f for f in video_dir.iterdir()
                if f.suffix != ".log" and (current is None or f != current)
            ]
            if len(video_paths) <= 1:
                logger.error("No more files to delete in %s", video_dir)
                raise OSError(f"No space and no files to delete in {video_dir}")
            oldest = min(video_paths, key=lambda p: p.stat().st_ctime)
            oldest.unlink()
            logger.info("Deleted %s", oldest)

    # --- Internal helpers ---

    def _split(self) -> None:
        previous_file = self._current_video_file
        new_file = self._video_filename()
        self._camera.split_recording(new_file)
        self._current_video_file = new_file
        logger.info("Split recording: %s", new_file)
        self._event_bus.publish(RecordingSplit(filename=previous_file))
        self.delete_old_files()

    def _wait_recording(self, timeout: int | float = 0) -> None:
        if self._camera.is_recording:
            self._camera.wait_recording(timeout)
        else:
            sleep(timeout)

    def _led_recording_on(self) -> None:
        led = self._leds.get("recording")
        if led:
            led.blink(on_time=0.1, off_time=4.9, n=None, background=True)

    def _led_recording_off(self) -> None:
        led = self._leds.get("recording")
        if led:
            led.pulse(fade_in_time=0.25, fade_out_time=0.25, n=4, background=True)

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
                timeout=10,
            )
            if response.status_code != 200:
                logger.warning("Preview send failed: %d", response.status_code)
            logger.debug("Preview sent to external server")
        except Exception as e:
            logger.warning("Error sending preview: %s", e)
```

- [ ] **Step 2: Write CameraController tests**

```python
# tests/controller/test_camera_controller.py
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest

from OTCamera.config import Config
from OTCamera.controller.camera_controller import CameraController
from OTCamera.domain.camera import Camera
from OTCamera.domain.events import (
    EventBus,
    PreviewCaptured,
    RecordingSplit,
    RecordingStarted,
    RecordingStopped,
)


@pytest.fixture
def mock_camera() -> MagicMock:
    camera = MagicMock(spec=Camera)
    type(camera).is_recording = PropertyMock(return_value=False)
    return camera


@pytest.fixture
def config(tmp_path: Path) -> Config:
    c = Config()
    c.video.dir = str(tmp_path)
    c.video.format = "h264"
    c.video.resolution = (640, 480)
    c.video.h264_bitrate = 600000
    c.video.h264_profile = "high"
    c.video.h264_level = "4"
    c.video.h264_quality = 30
    c.camera.fps = 20
    c.prefix = "test"
    c.preview.path = str(tmp_path / "preview.jpg")
    c.preview.format = "jpeg"
    c.preview.send_to_external = False
    c.recording.interval_length = 15
    c.recording.num_intervals = 0
    c.recording.min_free_space = 0
    return c


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


class TestStartRecording:
    def test_start_calls_camera(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        cc = CameraController(mock_camera, config, bus, {})
        type(mock_camera).is_recording = PropertyMock(side_effect=[False, True, True])
        cc.start_recording()
        mock_camera.start_recording.assert_called_once()

    def test_start_emits_event(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        received: list = []
        bus.subscribe(RecordingStarted, received.append)
        type(mock_camera).is_recording = PropertyMock(side_effect=[False, True, True])
        cc = CameraController(mock_camera, config, bus, {})
        cc.start_recording()
        bus.process_pending()
        assert len(received) == 1
        assert received[0].filename.endswith(".h264")

    def test_start_skips_if_already_recording(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        type(mock_camera).is_recording = PropertyMock(return_value=True)
        cc = CameraController(mock_camera, config, bus, {})
        cc.start_recording()
        mock_camera.start_recording.assert_not_called()


class TestStopRecording:
    def test_stop_calls_camera(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        type(mock_camera).is_recording = PropertyMock(return_value=True)
        cc = CameraController(mock_camera, config, bus, {})
        cc.stop_recording()
        mock_camera.stop_recording.assert_called_once()

    def test_stop_emits_event(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        received: list = []
        bus.subscribe(RecordingStopped, received.append)
        type(mock_camera).is_recording = PropertyMock(return_value=True)
        cc = CameraController(mock_camera, config, bus, {})
        cc.stop_recording()
        bus.process_pending()
        assert len(received) == 1

    def test_stop_skips_if_not_recording(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        type(mock_camera).is_recording = PropertyMock(return_value=False)
        cc = CameraController(mock_camera, config, bus, {})
        cc.stop_recording()
        mock_camera.stop_recording.assert_not_called()


class TestSplitRecording:
    def test_split_emits_event_with_previous_filename(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        received: list[RecordingSplit] = []
        bus.subscribe(RecordingSplit, received.append)
        type(mock_camera).is_recording = PropertyMock(return_value=True)
        cc = CameraController(mock_camera, config, bus, {})
        previous = cc._current_video_file
        cc._last_split_minute = -1
        # Force a split by setting last_split_minute to something other than current
        from unittest.mock import patch
        from datetime import datetime

        with patch(
            "OTCamera.controller.camera_controller.dt"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 1, 12, 0, 0)
            mock_dt.strftime = datetime.strftime
            cc.split_if_interval_ends()

        bus.process_pending()
        if received:
            assert received[0].filename == previous


class TestDeleteOldFiles:
    def test_deletes_oldest_file(
        self, mock_camera: MagicMock, config: Config, bus: EventBus, tmp_path: Path
    ) -> None:
        config.recording.min_free_space = 999  # force deletion
        (tmp_path / "old.h264").write_bytes(b"x" * 100)
        (tmp_path / "new.h264").write_bytes(b"x" * 100)
        cc = CameraController(mock_camera, config, bus, {})
        with pytest.raises(OSError):
            cc.delete_old_files()
        # At least one file should remain (the last one triggers OSError)

    def test_no_files_raises_oserror(
        self, mock_camera: MagicMock, config: Config, bus: EventBus, tmp_path: Path
    ) -> None:
        config.recording.min_free_space = 999
        cc = CameraController(mock_camera, config, bus, {})
        with pytest.raises(OSError, match="No space"):
            cc.delete_old_files()


class TestFilenameGeneration:
    def test_video_filename_contains_prefix_and_fps(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        cc = CameraController(mock_camera, config, bus, {})
        filename = cc._video_filename()
        assert "test" in filename
        assert "FR20" in filename
        assert filename.endswith(".h264")

    def test_video_filename_uses_config_format(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        config.video.format = "h264"
        cc = CameraController(mock_camera, config, bus, {})
        assert cc._video_filename().endswith(".h264")


class TestLEDInteraction:
    def test_recording_led_blinks_on_start(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        mock_led = MagicMock()
        type(mock_camera).is_recording = PropertyMock(side_effect=[False, True, True])
        cc = CameraController(mock_camera, config, bus, {"recording": mock_led})
        cc.start_recording()
        mock_led.blink.assert_called()

    def test_no_led_does_not_crash(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        type(mock_camera).is_recording = PropertyMock(side_effect=[False, True, True])
        cc = CameraController(mock_camera, config, bus, {})
        cc.start_recording()  # should not raise


class TestClose:
    def test_close_calls_camera_close(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        cc = CameraController(mock_camera, config, bus, {})
        cc.close()
        mock_camera.close.assert_called_once()

    def test_close_handles_already_closed(
        self, mock_camera: MagicMock, config: Config, bus: EventBus
    ) -> None:
        from OTCamera.domain.camera import CameraClosedError

        mock_camera.close.side_effect = CameraClosedError()
        cc = CameraController(mock_camera, config, bus, {})
        cc.close()  # should not raise
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/controller/test_camera_controller.py -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add OTCamera/controller/camera_controller.py tests/controller/test_camera_controller.py
git commit -m "feat: add CameraController with recording orchestration"
```

---

### Task 17: UploadController

**Files:**
- Create: `OTCamera/controller/upload_controller.py`

- [ ] **Step 1: Implement UploadController**

```python
# OTCamera/controller/upload_controller.py
"""Upload controller that subscribes to recording events."""

import logging

from OTCamera.domain.events import EventBus, RecordingSplit
from OTCamera.domain.upload import Upload

logger = logging.getLogger(__name__)


class UploadController:
    """Subscribes to RecordingSplit events and uploads completed files."""

    def __init__(self, event_bus: EventBus, upload: Upload | None = None) -> None:
        self._upload = upload
        if upload:
            event_bus.subscribe(RecordingSplit, self._on_recording_split)
            logger.debug("Upload controller active")

    def _on_recording_split(self, event: RecordingSplit) -> None:
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

### Task 18: Logging module (OTCamera/log.py)

**Files:**
- Create: `OTCamera/log.py`

- [ ] **Step 1: Implement log.py**

```python
# OTCamera/log.py
"""OTCamera logging setup.

Configures Python standard logging with FileHandler, StreamHandler,
and optional MsTeamsHandler. Call setup_logging(config) once during wiring.
"""

import json
import logging
from datetime import datetime as dt
from pathlib import Path

import requests

from OTCamera.config import Config


class MsTeamsHandler(logging.Handler):
    """Logging handler that posts messages to MS Teams webhook."""

    def __init__(self, webhook_url: str, max_failures: int = 2) -> None:
        super().__init__()
        self._webhook_url = webhook_url
        self._max_failures = max_failures
        self._failed_attempts = 0
        self._disabled = False

    def emit(self, record: logging.LogRecord) -> None:
        if self._disabled:
            return
        if record.levelno <= logging.DEBUG:
            return

        msg = self.format(record)
        try:
            response = requests.post(
                self._webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps({"text": msg}),
                timeout=10,
            )
            if response.status_code in range(400, 600):
                self._failed_attempts += 1
            else:
                self._failed_attempts = 0
        except requests.exceptions.RequestException:
            self._failed_attempts += 1

        if self._failed_attempts >= self._max_failures:
            self._disabled = True


def _log_file_path(config: Config) -> Path:
    """Generate logfile path from config."""
    timestamp = dt.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = Path(config.video.dir) / f"{config.prefix}_FR{config.camera.fps}_{timestamp}.log"
    return filename.expanduser().resolve()


def setup_logging(config: Config) -> None:
    """Configure logging handlers and formatters.

    Must be called once during wiring, after config is parsed.
    """
    log_path = _log_file_path(config)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if config.debug_mode_on else logging.INFO
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(str(log_path), mode="a")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Stream handler (stdout)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # MS Teams handler (optional)
    if config.msteams.enable and config.msteams.url:
        teams_handler = MsTeamsHandler(
            webhook_url=config.msteams.url,
            max_failures=config.msteams.max_failed_send_attempts,
        )
        teams_handler.setFormatter(formatter)
        root_logger.addHandler(teams_handler)
```

- [ ] **Step 2: Commit**

```bash
git add OTCamera/log.py
git commit -m "feat: add logging module with setup_logging and MsTeamsHandler"
```

---

### Task 19: Rewrite __main__.py (wiring + main loop)

**Files:**
- Rewrite: `OTCamera/__main__.py`

- [ ] **Step 1: Rewrite __main__.py**

```python
# OTCamera/__main__.py
"""OTCamera entry point.

Wires all components together and runs the main recording loop.
"""

import logging
import re
import signal
from datetime import datetime as dt
from datetime import timedelta
from pathlib import Path
from time import sleep
from typing import Any, Iterator

import psutil

from OTCamera.bsl.board_provider import BoardProvider
from OTCamera.config import Config, parse_user_config
from OTCamera.controller.camera_controller import CameraController
from OTCamera.controller.power_controller import PowerController
from OTCamera.controller.schedule_controller import ScheduleController
from OTCamera.controller.upload_controller import UploadController
from OTCamera.controller.wifi_controller import WifiController
from OTCamera.domain.events import (
    ButtonHeld,
    ButtonPressed,
    ButtonReleased,
    EventBus,
    ShutdownRequested,
)
from OTCamera.domain.led import LED
from OTCamera.html_updater import (
    ConfigDataObject,
    ConfigHtmlId,
    LogDataObject,
    LogHtmlId,
    StatusDataObject,
    StatusHtmlId,
    StatusWebsiteUpdater,
)
from OTCamera.log import setup_logging
from OTCamera.module.camera.camera_provider import CameraProvider
from OTCamera.plugin.upload.upload_provider import UploadProvider

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
        leds: dict[str, LED],
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
        signal.signal(signal.SIGINT, self._execute_shutdown)
        event_bus.subscribe(ShutdownRequested, self._on_shutdown_requested)
        Path(config.video.dir).mkdir(parents=True, exist_ok=True)

    def record(self) -> None:
        logger.info("Starting periodic record")
        self._send_alive_signal()

        try:
            while self._camera.more_intervals and not self._shutdown:
                try:
                    self._loop()
                except OSError as oe:
                    if oe.errno == 28:  # ENOSPC
                        logger.exception("No space left on device")
                        self._camera.delete_old_files()
                    else:
                        raise
            if not self._shutdown:
                logger.info("Captured all intervals, stopping")
        except KeyboardInterrupt:
            logger.info("Keyboard Interrupt, stopping")
        except Exception:
            logger.exception("Unhandled exception in main loop")
            raise
        finally:
            self._execute_shutdown()

    def _loop(self) -> None:
        # Dispatch enqueued button events from gpiozero background threads
        self._event_bus.process_pending()
        self._power.check_power_status()
        self._power.check_pending_shutdown()
        self._wifi.check_pending_wifi_off()
        self._send_alive_signal()

        if self._shutdown:
            return

        if self._schedule.should_record():
            self._camera.start_recording()
            self._camera.split_if_interval_ends()
            self._try_capture_preview()
        else:
            self._camera.stop_recording()
            self._update_html()
            sleep(0.5)

    def _send_alive_signal(self) -> None:
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
        current_second = dt.now().second
        interval = self._config.preview.interval
        offset = interval - 1
        is_preview_time = (current_second % interval) == offset
        should_capture = (
            is_preview_time
            and self._wifi.wifi_on
            and not self._preview_taken
            and not self._schedule.shutdown_active
        )
        if should_capture:
            self._camera.capture()
            self._update_html()
            self._preview_taken = True
        elif not is_preview_time and self._preview_taken:
            self._preview_taken = False

    def _update_html(self) -> None:
        if self._shutdown:
            return
        self._html_updater.update_info(
            status_info=self._get_status_data(),
            config_info=self._get_config_settings(),
            currently_recording=self._camera.is_recording,
            always_recording=self._schedule.is_24_7_mode,
            external_power_supply_connected=self._power.external_power_connected,
        )

    def _get_status_data(self) -> StatusDataObject:
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
                time_until_wifi_off = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
            else:
                time_until_wifi_off = "00:00:00"

        return StatusDataObject(
            free_diskspace=(StatusHtmlId.FREE_DISKSPACE, f"{free_gb:.2f} GB"),
            num_videos_recorded=(StatusHtmlId.NUM_VIDEOS_RECORDED, num_videos),
            currently_recording=(StatusHtmlId.CURRENTLY_RECORDING, self._camera.is_recording),
            low_battery=(StatusHtmlId.LOW_BATTERY, self._power.battery_is_low),
            hour_button_active=(StatusHtmlId.HOUR_BUTTON_ACTIVE, self._schedule.is_24_7_mode),
            external_power_supply_connected=(
                StatusHtmlId.EXT_POWER_SUPPLY_CONNECTED,
                self._power.external_power_connected,
            ),
            ms_teams_webhook_enabled=(
                StatusHtmlId.MS_TEAMS_WEBHOOK_ENABLED,
                self._config.msteams.enable,
            ),
            time_until_wifi_off=(StatusHtmlId.TIME_UNTIL_WIFI_OFF, time_until_wifi_off),
        )

    def _get_config_settings(self) -> ConfigDataObject:
        c = self._config
        return ConfigDataObject(
            debug_mode_on=(ConfigHtmlId.DEBUG_MODE_ON, c.debug_mode_on),
            start_hour=(ConfigHtmlId.START_HOUR, c.recording.start_hour),
            end_hour=(ConfigHtmlId.END_HOUR, c.recording.end_hour),
            interval_video_split=(ConfigHtmlId.INTERVAL_VIDEO_SPLIT, c.recording.interval_length),
            num_intervals=(ConfigHtmlId.NUM_INTERVALS, c.recording.num_intervals),
            preview_interval=(ConfigHtmlId.PREVIEW_INTERVAL, c.preview.interval),
            min_free_space=(ConfigHtmlId.MIN_FREE_SPACE, c.recording.min_free_space),
            prefix=(ConfigHtmlId.PREFIX, c.prefix),
            video_dir=(ConfigHtmlId.VIDEO_DIR, c.video.dir),
            preview_path=(ConfigHtmlId.PREVIEW_PATH, c.preview.path),
            template_html_path=(ConfigHtmlId.TEMPLATE_HTML_PATH, c.template_html_path),
            index_html_path=(ConfigHtmlId.INDEX_HTML_PATH, c.index_html_path),
            fps=(ConfigHtmlId.FPS, c.camera.fps),
            resolution=(ConfigHtmlId.RESOLUTION, c.camera.resolution),
            exposure_mode=(ConfigHtmlId.EXPOSURE_MODE, c.camera.exposure_mode),
            drc_strength=(ConfigHtmlId.DRC_STRENGTH, c.camera.drc_strength),
            rotation=(ConfigHtmlId.ROTATION, c.camera.rotation),
            awb_mode=(ConfigHtmlId.AWB_MODE, c.camera.awb_mode),
            video_format=(ConfigHtmlId.VIDEO_FORMAT, c.video.format),
            preview_format=(ConfigHtmlId.PREVIEW_FORMAT, c.preview.format),
            res_of_saved_video_file=(ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE, c.video.resolution),
            h264_profile=(ConfigHtmlId.H264_PROFILE, c.video.h264_profile),
            h264_level=(ConfigHtmlId.H264_LEVEL, c.video.h264_level),
            h264_bitrate=(ConfigHtmlId.H264_BITRATE, c.video.h264_bitrate),
            h264_quality=(ConfigHtmlId.H264_QUALITY, c.video.h264_quality),
            use_led=(ConfigHtmlId.USE_LED, c.hardware.use_leds),
            use_buttons=(ConfigHtmlId.USE_BUTTONS, c.hardware.use_buttons),
            wifi_delay=(ConfigHtmlId.WIFI_DELAY, c.wifi.delay),
        )

    def _get_log_info(self, start_idx: int, num: int) -> LogDataObject:
        log_dir = Path(self._config.video.dir).expanduser().resolve()
        if not log_dir.is_dir():
            return LogDataObject(log_data=(LogHtmlId.LOG_DATA, ""))
        sorted_logs = _get_log_files_sorted(log_dir.iterdir())
        recent = sorted_logs[start_idx:start_idx + num]
        recent.reverse()
        log_data = ""
        for log_file_path in recent:
            log_data += f"File: {log_file_path}\n"
            with open(log_file_path, "r") as f:
                log_data += f.read() + "\n"
        return LogDataObject(log_data=(LogHtmlId.LOG_DATA, log_data))

    def _on_shutdown_requested(self, event: ShutdownRequested) -> None:
        self._execute_shutdown()

    def _execute_shutdown(self, *args: Any) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        logger.info("Stopping OTCamera")
        self._schedule.set_shutdown_active(True)
        self._camera.stop_recording()
        self._camera.close()
        logger.info("OTCamera stopped")
        self._html_updater.display_offline_info(
            self._get_log_info(0, self._config.num_log_files_html),
        )


def _get_log_files_sorted(log_files: Iterator[Path]) -> list[Path]:
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


def main(config: Config | None = None, config_file: str = "~/user_config.yaml") -> None:
    """Wire up all components and start recording."""
    if config is None:
        config = parse_user_config(config_file)

    setup_logging(config)

    event_bus = EventBus()

    # BSL
    board = BoardProvider.provide(config)

    camera = None
    upload = None
    try:
        # Module
        camera = CameraProvider.provide(config)

        # Plugin
        upload = UploadProvider.provide(config)

        # Controllers
        camera_controller = CameraController(camera, config, event_bus, board.leds)
        power_controller = PowerController(
            config, event_bus, board.leds, board.adc, board.adc_config
        )
        wifi_controller = WifiController(config, event_bus, board.leds)
        schedule_controller = ScheduleController(config, event_bus)
        upload_controller = UploadController(event_bus, upload)  # noqa: F841

        # Wire buttons to event bus
        for name, button in board.buttons.items():
            button.on_pressed(lambda n=name: event_bus.enqueue(ButtonPressed(n)))
            button.on_released(lambda n=name: event_bus.enqueue(ButtonReleased(n)))
            button.on_held(lambda n=name: event_bus.enqueue(ButtonHeld(n)))

        # Boot checks — abort before further init if shutdown is needed
        if "power" in board.buttons and not board.buttons["power"].is_pressed:
            logger.info("Power switch OFF at boot — immediate shutdown")
            power_controller.shutdown(source="boot")
            return

        if power_controller.has_adc and power_controller.is_low_battery:
            logger.warning("Battery low at startup!")
            power_controller.shutdown(source="battery")
            return

        # Reconcile initial switch positions
        if "wifi" in board.buttons:
            wifi_controller.init_from_switch(board.buttons["wifi"].is_pressed)
        if "hour" in board.buttons:
            schedule_controller.init_from_switch(board.buttons["hour"].is_pressed)

        # HTML updater
        html_updater = StatusWebsiteUpdater(
            template_html_path=config.template_html_path,
            offline_html_path=config.offline_html_path,
            html_save_path=config.index_html_path,
            debug_mode_on=config.debug_mode_on,
        )

        # Process any pending events from init_from_switch
        event_bus.process_pending()

        Path(config.video.dir).mkdir(parents=True, exist_ok=True)

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

    finally:
        for resource in [camera, upload]:
            if resource:
                try:
                    resource.close()
                except Exception:
                    logger.debug("Error closing resource", exc_info=True)
        board.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add OTCamera/__main__.py
git commit -m "refactor: rewrite __main__.py with BSL/module/plugin wiring and queue-based event bus"
```

---

### Task 20: Update run.py

**Files:**
- Modify: `run.py`

- [ ] **Step 1: Rewrite run.py**

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
        import usb_flash_drive_copy

        usb_flash_drive_copy.main(config)
    else:
        from OTCamera.__main__ import main as otcamera_main

        otcamera_main(config=config)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add run.py
git commit -m "refactor: update run.py for new config and entry points"
```

---

### Task 21: Update usb_flash_drive_copy.py

**Files:**
- Modify: `usb_flash_drive_copy.py`

- [ ] **Step 1: Update imports**

Replace the top imports:

```python
# REMOVE:
from gpiozero import PWMLED
from gpiozero import Button as GPIOButton
import OTCamera.config as config
import OTCamera.helpers.log as log

# ADD:
import logging

from OTCamera.bsl.board_provider import BoardComponents, BoardProvider
from OTCamera.config import Config
from OTCamera.log import setup_logging

logger = logging.getLogger(__name__)
```

- [ ] **Step 2: Replace Led wrapper class**

Replace the `Led` class with a version that wraps the domain `LED` ABC:

```python
class Led:
    def __init__(self, led: "LED | None") -> None:
        self._led = led

    def blink(self, times: int | None = None, background: bool = True) -> None:
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

Add import at top: `from OTCamera.domain.led import LED`

- [ ] **Step 3: Replace Button class**

Replace the `Button` class to use domain `Button` ABC from BoardProvider:

```python
class PowerButton:
    """Monitors power button for shutdown request."""

    def __init__(self, button: "DomainButton") -> None:
        self._button = button
        self.shutdown_requested = False
        self._button.on_released(self._on_released)
        if not self._button.is_pressed:
            raise IllegalStateError(
                "Power button must be active for the script to run"
            )

    def _on_released(self) -> None:
        logger.debug("Power button released")
        self.shutdown_requested = True
```

Add import at top: `from OTCamera.domain.button import Button as DomainButton`

- [ ] **Step 4: Replace build_usb_copier function**

```python
def build_usb_copier(
    config: Config, board: BoardComponents
) -> tuple[OTCameraUsbCopier, PowerButton | None]:
    src_dir = Path(config.video.dir)
    usb_flash_drive = UsbFlashDrive(Path(config.usb_mount_point))

    power_led = Led(board.leds.get("power"))
    rec_led = Led(board.leds.get("recording"))
    wifi_led = Led(board.leds.get("wifi"))

    usb_copier = OTCameraUsbCopier(
        power_led, wifi_led, rec_led, src_dir, usb_flash_drive,
        debug_mode_on=config.debug_mode_on,
    )

    power_button: PowerButton | None = None
    if config.hardware.use_buttons and "power" in board.buttons:
        power_button = PowerButton(board.buttons["power"])

    return usb_copier, power_button
```

- [ ] **Step 5: Update OTCameraUsbCopier class**

Remove `Observer` inheritance. Add `debug_mode_on` parameter:

```python
class OTCameraUsbCopier:
    def __init__(
        self,
        power_led: Led,
        wifi_led: Led,
        rec_led: Led,
        src_dir: Path,
        usb_flash_drive: UsbFlashDrive,
        debug_mode_on: bool = False,
    ) -> None:
        self.power_led = power_led
        self.wifi_led = wifi_led
        self.rec_led = rec_led
        self.src_dir = src_dir
        self.usb_flash_drive = usb_flash_drive
        self.debug_mode_on = debug_mode_on
```

Replace all `config.DEBUG_MODE_ON` with `self.debug_mode_on`.
Replace all `log.write(msg, level)` with `logger.info(msg)` / `logger.warning(msg)` / `logger.debug(msg)` / `logger.exception(msg)`.
Replace `log.closefile()` calls with nothing (logging handles cleanup).
Replace `subprocess.call("sudo shutdown -h now", shell=True)` with `subprocess.call(["sudo", "shutdown", "-h", "now"])`.

- [ ] **Step 6: Rewrite main function**

```python
def main(config: Config) -> None:
    """Start the OTCamera USB copy script."""
    setup_logging(config)

    # Note: USB copy only needs LEDs/buttons, not ADC. Consider
    # using dataclasses.replace(config.hardware, use_adc=False) to
    # skip ADC init on hardware where ADC is absent.
    board = BoardProvider.provide(config)
    try:
        usb_copier, power_button = build_usb_copier(config, board)
        src_dir = Path(config.video.dir)
        usb_device_mount = Path(config.usb_mount_point)
        dest_dir = Path(usb_device_mount, get_hostname())
        usb_copy_info_path = CopyInformation.get_copy_info_csv(dest_dir)

        usb_copier.mount_usb_device()
        if usb_copy_info_path.exists():
            usb_copy_info = CopyInformation.from_csv(
                usb_copy_info_path, src_dir, dest_dir
            )
        else:
            usb_copy_info = CopyInformation.create_new(
                src_dir, dest_dir, config.video.format
            )

        usb_copier.copy_to_usb(usb_copy_info)
        usb_copier.delete(usb_copy_info)
        usb_copier.write_copy_info(usb_copy_info)
        usb_copier.unmount_usb_device()

        if power_button is not None:
            while not power_button.shutdown_requested:
                time.sleep(0.1)
            usb_copier.shutdown()

    except Exception:
        logger.exception("USB copy failed")
    finally:
        board.close()
```

- [ ] **Step 7: Remove Subject/Observer ABC classes**

Delete the `Subject` and `Observer` ABC classes — no longer needed. Remove the `update()` method from `OTCameraUsbCopier`.

- [ ] **Step 8: Commit**

```bash
git add usb_flash_drive_copy.py
git commit -m "refactor: update usb_flash_drive_copy for new config and BoardProvider"
```

---

### Task 22: Cleanup — delete old files and directories

**Files to delete:**
- `OTCamera/hardware/` (entire directory)
- `OTCamera/plugin/adc/` (entire directory)
- `OTCamera/plugin/camera/picamerax.py` (if not already deleted)
- `OTCamera/plugin_ftp_server/` (entire directory)
- `OTCamera/helpers/name.py`
- `OTCamera/helpers/filesystem.py`
- `OTCamera/helpers/rpi.py`
- `OTCamera/helpers/errors.py`
- `OTCamera/helpers/log.py`
- `OTCamera/helpers/` (entire directory)
- `OTCamera/record.py`
- `OTCamera/status.py`
- `OTCamera/domain/camera_errors.py` (if not already deleted)
- `OTCamera/abstraction/` (entire directory)

- [ ] **Step 1: Delete old files**

```bash
rm -rf OTCamera/hardware/
rm -rf OTCamera/plugin/adc/
rm -f OTCamera/plugin/camera/picamerax.py
rm -rf OTCamera/plugin_ftp_server/
rm -rf OTCamera/helpers/
rm -f OTCamera/record.py
rm -f OTCamera/status.py
rm -f OTCamera/domain/camera_errors.py
rm -rf OTCamera/abstraction/
```

- [ ] **Step 2: Search for and fix any remaining old imports**

```bash
grep -r "from OTCamera.hardware" OTCamera/ tests/
grep -r "from OTCamera.helpers" OTCamera/ tests/
grep -r "from OTCamera.record" OTCamera/ tests/
grep -r "from OTCamera.status" OTCamera/ tests/
grep -r "from OTCamera.plugin_ftp_server" OTCamera/ tests/
grep -r "from OTCamera.plugin.adc" OTCamera/ tests/
grep -r "from OTCamera.abstraction" OTCamera/ tests/
grep -r "from OTCamera.domain.camera_errors" OTCamera/ tests/
```

Fix all found references. In particular: `html_updater.py` imports `from OTCamera.helpers import log` — replace with `import logging` / `logger = logging.getLogger(__name__)` and replace all `log.write()` calls with `logger.info()` / `logger.warning()` etc.

- [ ] **Step 3: Remove empty plugin/camera directory if only __init__.py remains**

Check `OTCamera/plugin/camera/` — if only `__init__.py` and `camera_provider.py` remain (old provider), delete them. The new provider is in `module/camera/`.

```bash
rm -rf OTCamera/plugin/camera/
```

- [ ] **Step 4: Update example and test config files**

Update `user_config.example.yaml` and `tests/test_user_config.yaml`:
- `hardware.pcb_version`: `v1` → `v2`
- `leds.enable` / `buttons.enable` → `hardware.use_leds` / `hardware.use_buttons`
- `server_upload.upload` → `server_upload.enable`
- Remove any config keys that no longer exist (GPIO pins, ADC hardware params — now in board definitions)

- [ ] **Step 5: Update requirements.txt**

- Remove `picamerax` (legacy backend dropped)
- Remove `RPi.GPIO` (replaced by lgpio on Trixie)
- Remove `art` (ASCII logo removed with old log.py)
- Add `smbus2` (TLA2024 ADC, Linux-only)
- Add `lgpio` (gpiozero pin factory on Trixie, Linux-only)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete old files, update config examples for new architecture"
```

---

### Task 23: Update existing tests

**Files:**
- Delete: `tests/helpers/name_test.py` (logic moved to CameraController)
- Delete: `tests/helpers/filesystem_test.py` (logic moved to CameraController)
- Delete: `tests/record_test.py` (logic moved to __main__.py)
- Modify: `tests/hardware/camera_test.py` (update imports)
- Modify: `tests/html_updater_test.py` (fix constructor and method signatures)
- Modify: `tests/conftest.py` (if needed)
- Modify: `pyproject.toml` (add testpaths)

- [ ] **Step 1: Delete obsolete test files**

```bash
rm -f tests/helpers/name_test.py
rm -f tests/helpers/filesystem_test.py
rm -f tests/record_test.py
rm -rf tests/helpers/
```

- [ ] **Step 2: Update camera_test.py imports**

Update `tests/hardware/camera_test.py` to import from new locations:
- `from OTCamera.module.camera.camera_provider import CameraProvider`
- `from OTCamera.domain.camera import CameraClosedError`
- Add `pytest.importorskip("picamera2")` at top of file so tests are skipped on non-Pi machines

- [ ] **Step 3: Fix html_updater_test.py**

Update the `StatusWebsiteUpdater` constructor call to match the current signature (add required path args from test fixtures). Update `update_info()` calls to match the current method signature.

- [ ] **Step 4: Add testpaths to pyproject.toml**

Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 5: Run all tests**

Run: `pytest -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "test: update tests for new architecture, add testpaths config"
```

---

### Task 24: Rename hardware_test.py to hardware_check.py

**Files:**
- Delete: `hardware_test.py`
- Create: `hardware_check.py`

- [ ] **Step 1: Rename and rewrite**

Rewrite `hardware_test.py` as `hardware_check.py`:
- Replace `picamerax.PiCamera()` with `CameraProvider.provide(config)`
- Replace direct GPIO with `BoardProvider.provide(config)` for LEDs, buttons, ADC
- Load config via `parse_user_config()`
- Add ADC test commands (battery voltage, USB voltage)
- Call `board.close()` in finally block

- [ ] **Step 2: Commit**

```bash
git add hardware_check.py
git rm hardware_test.py
git commit -m "refactor: rename hardware_test.py to hardware_check.py, update for new architecture"
```

---

### Task 25: Final verification

- [ ] **Step 1: Run full test suite**

```bash
pytest -v --tb=short
```

- [ ] **Step 2: Run linting and type checking**

```bash
pre-commit run --all-files
```

- [ ] **Step 3: Verify directory structure matches design**

```bash
find OTCamera -type f -name "*.py" | sort
```

Expected structure should match the design doc directory structure.

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final cleanup and lint fixes"
```

---

### Task 26: Rename CLAUDE.md to AGENTS.md and update

**Files:**
- Rename: `CLAUDE.md` → `AGENTS.md`

- [ ] **Step 1: Rename and update**

Rename `CLAUDE.md` to `AGENTS.md`. Update to reflect the new architecture:
- Directory structure (domain/, bsl/, module/, plugin/, controller/)
- New entry points (run.py branching, usb_flash_drive_copy with BoardProvider)
- New config structure (nested dataclasses, hardware toggles)
- New test structure (tests/domain/, tests/bsl/, tests/controller/)
- Remove references to deleted modules (hardware/, helpers/, status.py, record.py, plugin_ftp_server/, abstraction/)
- Update commands if needed (Python >=3.11)

- [ ] **Step 2: Commit**

```bash
git mv CLAUDE.md AGENTS.md
git add AGENTS.md
git commit -m "docs: rename CLAUDE.md to AGENTS.md, update for new architecture"
```
