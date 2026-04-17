from unittest.mock import patch

from OTCamera.config import Config
from OTCamera.controller.schedule_controller import ScheduleController
from OTCamera.domain.events import ButtonPressed, ButtonReleased, EventBus


def _build_schedule_controller() -> tuple[Config, EventBus, ScheduleController]:
    config = Config(site_name="test-site", project_name="test-project")
    config.recording.start_hour = 6
    config.recording.end_hour = 22
    bus = EventBus()
    controller = ScheduleController(config, bus)
    return config, bus, controller


def test_should_record_within_hours() -> None:
    _, _, controller = _build_schedule_controller()
    with patch.object(controller, "_current_hour", return_value=12):
        assert controller.should_record() is True


def test_should_not_record_outside_hours() -> None:
    _, _, controller = _build_schedule_controller()
    with patch.object(controller, "_current_hour", return_value=23):
        assert controller.should_record() is False


def test_overnight_window() -> None:
    config, _, controller = _build_schedule_controller()
    config.recording.start_hour = 22
    config.recording.end_hour = 6
    with patch.object(controller, "_current_hour", return_value=23):
        assert controller.should_record() is True
    with patch.object(controller, "_current_hour", return_value=3):
        assert controller.should_record() is True
    with patch.object(controller, "_current_hour", return_value=12):
        assert controller.should_record() is False


def test_hour_switch_enables_and_disables_247_mode() -> None:
    _, bus, controller = _build_schedule_controller()
    bus.enqueue(ButtonPressed(name="hour"))
    bus.enqueue(ButtonReleased(name="hour"))
    bus.process_pending()

    with patch.object(controller, "_current_hour", return_value=23):
        assert controller.should_record() is False


def test_init_from_switch_on() -> None:
    _, _, controller = _build_schedule_controller()
    controller.init_from_switch(True)

    with patch.object(controller, "_current_hour", return_value=23):
        assert controller.should_record() is True


def test_shutdown_active_disables_recording() -> None:
    _, _, controller = _build_schedule_controller()
    controller.set_shutdown_active(True)

    with patch.object(controller, "_current_hour", return_value=12):
        assert controller.should_record() is False
