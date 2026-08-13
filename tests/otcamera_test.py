from pathlib import Path
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from OTCamera.__main__ import OTCamera
from OTCamera.config import Config
from OTCamera.controller.backlog import Backlog
from OTCamera.domain.events import EventBus


def test_execute_shutdown_stops_recording_without_closing_camera(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = Config()
    config.video.dir = str(tmp_path)

    event_bus = EventBus()
    camera_controller = MagicMock()
    power_controller = MagicMock()
    wifi_controller = MagicMock()
    schedule_controller = MagicMock()
    html_updater = MagicMock()

    monkeypatch.setattr("OTCamera.__main__.signal.signal", lambda *_args: None)

    app = OTCamera(
        config=config,
        event_bus=event_bus,
        camera_controller=camera_controller,
        power_controller=power_controller,
        wifi_controller=wifi_controller,
        schedule_controller=schedule_controller,
        html_updater=html_updater,
        leds={},
        backlog=Backlog(
            video_dir=tmp_path, video_format=config.video.format, min_free_bytes=0
        ),
    )

    app._execute_shutdown()

    schedule_controller.set_shutdown_active.assert_called_once_with(True)
    camera_controller.stop_recording.assert_called_once_with()
    camera_controller.close.assert_not_called()
    html_updater.display_offline_info.assert_called_once()
