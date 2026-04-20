from datetime import datetime as dt
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

from OTCamera.config import Config
from OTCamera.controller.power_controller import _POWER_SHUTDOWN_DELAY, PowerController
from OTCamera.domain.adc import ADC, ADCConfig, ADCTimeoutError
from OTCamera.domain.events import (
    ButtonPressed,
    ButtonReleased,
    EventBus,
    ExternalPowerConnected,
    ShutdownRequested,
)


class FakeADC(ADC):
    def __init__(self) -> None:
        self.voltages = {0: 0.0, 2: 0.0}

    @property
    def channels(self) -> int:
        return 4

    def get_voltage(self, channel: int) -> float:
        return self.voltages.get(channel, 0.0)

    def close(self) -> None:
        return


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
    config = Config()
    config.adc.threshold_external_power = 2.5
    config.adc.threshold_low_battery = 3.3
    config.debug_mode = True
    return config


def test_power_controller_without_adc() -> None:
    bus = EventBus()
    controller = PowerController(Config(), bus, {})

    assert controller.has_adc is False
    assert controller.is_low_battery is False
    assert controller.is_external_power is False


def test_external_power_detected(config: Config, adc_config: ADCConfig) -> None:
    adc = FakeADC()
    adc.voltages[0] = 2.0
    bus = EventBus()
    controller = PowerController(config, bus, {}, adc, adc_config)

    assert controller.is_external_power is True


def test_low_battery_detected(config: Config, adc_config: ADCConfig) -> None:
    adc = FakeADC()
    adc.voltages[2] = 1.0
    bus = EventBus()
    controller = PowerController(config, bus, {}, adc, adc_config)

    assert controller.is_low_battery is True


def test_external_power_event_emitted(
    config: Config,
    adc_config: ADCConfig,
) -> None:
    adc = FakeADC()
    bus = EventBus()
    controller = PowerController(config, bus, {}, adc, adc_config)
    received: list[ExternalPowerConnected] = []
    bus.subscribe(ExternalPowerConnected, received.append)

    adc.voltages[0] = 2.0
    controller.check_power_status()

    assert len(received) == 1


def test_adc_timeout_battery_assumes_ok(
    config: Config,
    adc_config: ADCConfig,
) -> None:
    adc = MagicMock(spec=ADC)
    adc.get_voltage.side_effect = ADCTimeoutError("timeout")
    bus = EventBus()
    controller = PowerController(config, bus, {}, adc, adc_config)

    assert controller.is_low_battery is False


def test_power_button_countdown() -> None:
    bus = EventBus()
    controller = PowerController(Config(debug_mode=True), bus, {})
    bus.enqueue(ButtonReleased(name="power"))
    bus.process_pending()

    assert controller.shutdown_active is True

    bus.enqueue(ButtonPressed(name="power"))
    bus.process_pending()

    assert controller.shutdown_active is False


def test_countdown_expires_triggers_shutdown() -> None:
    bus = EventBus()
    received: list[ShutdownRequested] = []
    bus.subscribe(ShutdownRequested, received.append)
    controller = PowerController(Config(debug_mode=True), bus, {})
    bus.enqueue(ButtonReleased(name="power"))
    bus.process_pending()
    controller._power_off_time = dt.now() - timedelta(
        seconds=_POWER_SHUTDOWN_DELAY + 1,
    )

    controller.check_pending_shutdown()

    assert len(received) == 1
    assert received[0].source == "button"


def test_shutdown_closes_logging_before_os_shutdown(
    monkeypatch: MonkeyPatch,
) -> None:
    bus = EventBus()
    controller = PowerController(Config(debug_mode=False), bus, {})
    actions: list[object] = []

    def fake_call(command: list[str]) -> int:
        actions.append(("call", command))
        return 0

    def fake_logging_shutdown() -> None:
        actions.append("logging.shutdown")

    monkeypatch.setattr("OTCamera.controller.power_controller.call", fake_call)
    monkeypatch.setattr(
        "OTCamera.controller.power_controller.logging.shutdown",
        fake_logging_shutdown,
    )

    controller.shutdown(source="test")

    assert actions == [
        "logging.shutdown",
        ("call", ["sudo", "shutdown", "-h", "now"]),
    ]


def test_reboot_closes_logging_before_os_reboot(
    monkeypatch: MonkeyPatch,
) -> None:
    bus = EventBus()
    controller = PowerController(Config(debug_mode=False), bus, {})
    actions: list[object] = []

    def fake_call(command: list[str]) -> int:
        actions.append(("call", command))
        return 0

    def fake_logging_shutdown() -> None:
        actions.append("logging.shutdown")

    monkeypatch.setattr("OTCamera.controller.power_controller.call", fake_call)
    monkeypatch.setattr(
        "OTCamera.controller.power_controller.logging.shutdown",
        fake_logging_shutdown,
    )

    controller.reboot()

    assert actions == [
        "logging.shutdown",
        ("call", ["sudo", "reboot"]),
    ]
