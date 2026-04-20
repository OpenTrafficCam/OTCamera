from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from OTCamera.config import Config
from OTCamera.controller.camera_controller import CameraController
from OTCamera.domain.camera import Camera, CameraClosedError
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
    camera._recording = False
    type(camera).is_recording = PropertyMock(side_effect=lambda: camera._recording)
    camera.start_recording.side_effect = lambda **kwargs: setattr(
        camera, "_recording", True
    )
    camera.stop_recording.side_effect = lambda: setattr(camera, "_recording", False)
    camera.split_recording.side_effect = lambda path: setattr(
        camera, "_recording", True
    )
    return camera


@pytest.fixture
def config(default_config: Config, tmp_path: Path) -> Config:
    config = default_config
    config.video.dir = str(tmp_path)
    config.video.format = "h264"
    config.video.resolution = (640, 480)
    config.video.encoder.bitrate = 600000
    config.video.encoder.profile = "high"
    config.video.encoder.level = "4"
    config.video.encoder.quality = 30
    config.camera.fps = 20
    config.prefix = "test"
    config.preview.path = str(tmp_path / "preview.jpg")
    config.preview.format = "jpeg"
    config.preview.send_to_external = False
    config.recording.interval_length = 15
    config.recording.num_intervals = 0
    config.recording.min_free_space = 0
    return config


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


def test_start_calls_camera(
    mock_camera: MagicMock,
    config: Config,
    bus: EventBus,
) -> None:
    controller = CameraController(mock_camera, config, bus, {})

    controller.start_recording()

    mock_camera.start_recording.assert_called_once()


def test_start_emits_event(
    mock_camera: MagicMock,
    config: Config,
    bus: EventBus,
) -> None:
    received: list[RecordingStarted] = []
    bus.subscribe(RecordingStarted, received.append)
    controller = CameraController(mock_camera, config, bus, {})

    controller.start_recording()

    assert len(received) == 1
    assert received[0].filename.endswith(".h264")


def test_stop_emits_event(
    mock_camera: MagicMock,
    config: Config,
    bus: EventBus,
) -> None:
    received: list[RecordingStopped] = []
    bus.subscribe(RecordingStopped, received.append)
    controller = CameraController(mock_camera, config, bus, {})
    controller.start_recording()

    controller.stop_recording()

    assert len(received) == 1


def test_capture_emits_preview_event(
    mock_camera: MagicMock,
    config: Config,
    bus: EventBus,
) -> None:
    received: list[PreviewCaptured] = []
    bus.subscribe(PreviewCaptured, received.append)
    controller = CameraController(mock_camera, config, bus, {})
    controller.start_recording()

    controller.capture()

    assert len(received) >= 1
    assert received[-1].path.endswith("preview.jpg")


def test_split_emits_previous_filename(
    mock_camera: MagicMock,
    config: Config,
    bus: EventBus,
) -> None:
    received: list[RecordingSplit] = []
    bus.subscribe(RecordingSplit, received.append)
    controller = CameraController(mock_camera, config, bus, {})
    controller.start_recording()
    previous = controller._current_video_file

    with patch("OTCamera.controller.camera_controller.dt") as mocked_dt:
        from datetime import datetime

        mocked_dt.now.return_value = datetime(2026, 1, 1, 12, 0, 0)
        mocked_dt.strftime = datetime.strftime
        controller._last_split_minute = -1
        controller.split_if_interval_ends()

    assert received[0].filename == previous


def test_delete_old_files_raises_when_no_space(
    mock_camera: MagicMock,
    config: Config,
    bus: EventBus,
    tmp_path: Path,
) -> None:
    config.recording.min_free_space = 1
    (tmp_path / "old.h264").write_bytes(b"x")
    controller = CameraController(mock_camera, config, bus, {})

    with patch(
        "OTCamera.controller.camera_controller.psutil.disk_usage",
        return_value=SimpleNamespace(free=0),
    ):
        with pytest.raises(OSError):
            controller.delete_old_files()


def test_recording_led_blinks_on_start(
    mock_camera: MagicMock,
    config: Config,
    bus: EventBus,
) -> None:
    recording_led = MagicMock()
    controller = CameraController(
        mock_camera, config, bus, {"recording": recording_led}
    )

    controller.start_recording()

    recording_led.blink.assert_called()


def test_close_handles_already_closed(
    mock_camera: MagicMock,
    config: Config,
    bus: EventBus,
) -> None:
    mock_camera.close.side_effect = CameraClosedError()
    controller = CameraController(mock_camera, config, bus, {})

    controller.close()
