from datetime import datetime as dt
from datetime import timedelta

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
    config = Config()
    config.wifi.delay = 10
    config.debug_mode_on = True
    return config


def test_switch_pressed_turns_wifi_on(config: Config) -> None:
    bus = EventBus()
    controller = WifiController(config, bus, {})
    controller._wifi_on = False
    bus.enqueue(ButtonPressed(name="wifi"))
    bus.process_pending()

    assert controller.wifi_on is True


def test_switch_held_turns_wifi_on(config: Config) -> None:
    bus = EventBus()
    controller = WifiController(config, bus, {})
    controller._wifi_on = False
    bus.enqueue(ButtonHeld(name="wifi"))
    bus.process_pending()

    assert controller.wifi_on is True


def test_wifi_on_event_emitted(config: Config) -> None:
    bus = EventBus()
    controller = WifiController(config, bus, {})
    controller._wifi_on = False
    received: list[WifiOn] = []
    bus.subscribe(WifiOn, received.append)
    bus.enqueue(ButtonPressed(name="wifi"))
    bus.process_pending()

    assert len(received) == 1


def test_switch_released_starts_delay(config: Config) -> None:
    bus = EventBus()
    controller = WifiController(config, bus, {})
    bus.enqueue(ButtonReleased(name="wifi"))
    bus.process_pending()

    assert controller.switch_off_time is not None


def test_delayed_off_turns_wifi_off(config: Config) -> None:
    bus = EventBus()
    controller = WifiController(config, bus, {})
    controller._switch_off_time = dt.now() - timedelta(seconds=config.wifi.delay + 1)

    controller.check_pending_wifi_off()

    assert controller.wifi_on is False


def test_wifi_off_event_emitted(config: Config) -> None:
    bus = EventBus()
    controller = WifiController(config, bus, {})
    received: list[WifiOff] = []
    bus.subscribe(WifiOff, received.append)
    controller._switch_off_time = dt.now() - timedelta(seconds=config.wifi.delay + 1)

    controller.check_pending_wifi_off()

    assert len(received) == 1


def test_init_from_switch_off(config: Config) -> None:
    bus = EventBus()
    controller = WifiController(config, bus, {})

    controller.init_from_switch(False)

    assert controller.wifi_on is False


def test_other_buttons_ignored(config: Config) -> None:
    bus = EventBus()
    controller = WifiController(config, bus, {})
    controller._wifi_on = False
    bus.enqueue(ButtonPressed(name="power"))
    bus.enqueue(ButtonReleased(name="hour"))
    bus.process_pending()

    assert controller.wifi_on is False
    assert controller.switch_off_time is None
