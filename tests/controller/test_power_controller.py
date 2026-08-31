from datetime import datetime as dt
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

from OTCamera.config import Config
from OTCamera.controller.power_controller import (
    _BATTERY_WINDOW_SIZE,
    _POWER_SHUTDOWN_DELAY,
    PowerController,
    _battery_estimate,
)
from OTCamera.domain.adc import ADC, ADCConfig, ADCTimeoutError
from OTCamera.domain.events import (
    ButtonPressed,
    ButtonReleased,
    EventBus,
    ExternalPowerConnected,
    ShutdownRequested,
)
from tests.conftest import FakeClock


class FakeADC(ADC):
    def __init__(self) -> None:
        self.voltages = {0: 0.0, 2: 0.0}
        self.read_counts: dict[int, int] = {0: 0, 2: 0}

    @property
    def channels(self) -> int:
        return 4

    def get_voltage(self, channel: int) -> float:
        self.read_counts[channel] = self.read_counts.get(channel, 0) + 1
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
    controller = PowerController(config=Config(), event_bus=bus, leds={})

    assert controller.has_adc is False
    assert controller.battery_is_low is False
    assert controller.is_external_power is False


def test_external_power_detected(config: Config, adc_config: ADCConfig) -> None:
    adc = FakeADC()
    adc.voltages[0] = 2.0
    bus = EventBus()
    controller = PowerController(
        config=config,
        event_bus=bus,
        leds={},
        adc=adc,
        adc_config=adc_config,
        clock=FakeClock(),
    )

    assert controller.is_external_power is True


def test_battery_ok(config: Config, adc_config: ADCConfig) -> None:
    adc = FakeADC()
    adc.voltages[2] = 4.0
    bus = EventBus()
    clock = FakeClock()
    controller = PowerController(
        config=config,
        event_bus=bus,
        leds={},
        adc=adc,
        adc_config=adc_config,
        clock=clock,
    )

    for _ in range(_BATTERY_WINDOW_SIZE):
        controller.check_power_status()
        clock.advance(config.adc.battery_read_interval)

    assert controller.battery_is_low is False


def test_low_battery_detected(config: Config, adc_config: ADCConfig) -> None:
    adc = FakeADC()
    adc.voltages[2] = 1.0
    bus = EventBus()
    clock = FakeClock()
    controller = PowerController(
        config=config,
        event_bus=bus,
        leds={},
        adc=adc,
        adc_config=adc_config,
        clock=clock,
    )
    received: list[ShutdownRequested] = []
    bus.subscribe(ShutdownRequested, received.append)

    for _ in range(_BATTERY_WINDOW_SIZE):
        controller.check_power_status()
        clock.advance(config.adc.battery_read_interval)

    assert controller.battery_is_low is True
    assert len(received) == 1
    assert received[0].source == "battery"


def test_single_low_sample_does_not_trigger_low_battery(
    config: Config,
    adc_config: ADCConfig,
) -> None:
    """Regression test for bug 9930: one low Sample among high ones is not low."""
    adc = FakeADC()
    bus = EventBus()
    clock = FakeClock()
    controller = PowerController(
        config=config,
        event_bus=bus,
        leds={},
        adc=adc,
        adc_config=adc_config,
        clock=clock,
    )
    received: list[ShutdownRequested] = []
    bus.subscribe(ShutdownRequested, received.append)

    for voltage in [4.0, 4.0, 1.0, 4.0, 4.0]:
        adc.voltages[2] = voltage
        controller.check_power_status()
        clock.advance(config.adc.battery_read_interval)

    assert controller.battery_is_low is False
    assert received == []


def test_three_low_samples_do_not_trigger_low_battery(
    config: Config,
    adc_config: ADCConfig,
) -> None:
    """A single healthy Sample in the window vetoes the low-battery verdict."""
    adc = FakeADC()
    bus = EventBus()
    clock = FakeClock()
    controller = PowerController(
        config=config,
        event_bus=bus,
        leds={},
        adc=adc,
        adc_config=adc_config,
        clock=clock,
    )
    received: list[ShutdownRequested] = []
    bus.subscribe(ShutdownRequested, received.append)

    for voltage in [1.0, 4.0, 1.0, 1.0, 4.0]:
        adc.voltages[2] = voltage
        controller.check_power_status()
        clock.advance(config.adc.battery_read_interval)

    assert controller.battery_is_low is False
    assert received == []


def test_partly_filled_window_gives_no_verdict(
    config: Config,
    adc_config: ADCConfig,
) -> None:
    """Four low Samples are not enough; the window must be full."""
    adc = FakeADC()
    adc.voltages[2] = 1.0
    bus = EventBus()
    clock = FakeClock()
    controller = PowerController(
        config=config,
        event_bus=bus,
        leds={},
        adc=adc,
        adc_config=adc_config,
        clock=clock,
    )
    received: list[ShutdownRequested] = []
    bus.subscribe(ShutdownRequested, received.append)

    for _ in range(_BATTERY_WINDOW_SIZE - 1):
        controller.check_power_status()
        clock.advance(config.adc.battery_read_interval)

    assert controller.battery_is_low is False
    assert received == []


def test_battery_reads_gated_by_configured_interval(
    config: Config,
    adc_config: ADCConfig,
) -> None:
    adc = FakeADC()
    bus = EventBus()
    clock = FakeClock()
    controller = PowerController(
        config=config,
        event_bus=bus,
        leds={},
        adc=adc,
        adc_config=adc_config,
        clock=clock,
    )

    for _ in range(20):
        controller.check_power_status()
        clock.advance(1.0)

    assert adc.read_counts[2] == 2


def test_external_power_event_emitted(
    config: Config,
    adc_config: ADCConfig,
) -> None:
    adc = FakeADC()
    bus = EventBus()
    clock = FakeClock()
    controller = PowerController(
        config=config,
        event_bus=bus,
        leds={},
        adc=adc,
        adc_config=adc_config,
        clock=clock,
    )
    received: list[ExternalPowerConnected] = []
    bus.subscribe(ExternalPowerConnected, received.append)

    adc.voltages[0] = 2.0
    controller.check_power_status()

    assert len(received) == 1


def test_battery_estimate_needs_a_full_window() -> None:
    assert _battery_estimate(()) is None
    assert _battery_estimate((1.0, 1.0, 1.0, 1.0)) is None
    assert _battery_estimate((1.0, 4.0, 1.0, 1.0, 4.0)) == 4.0
    assert _battery_estimate((1.0, 1.0, 1.0, 1.0, 1.0)) == 1.0


def test_adc_timeout_does_not_raise_and_does_not_shut_down(
    config: Config,
    adc_config: ADCConfig,
) -> None:
    adc = MagicMock(spec=ADC)
    adc.get_voltage.side_effect = ADCTimeoutError("timeout")
    bus = EventBus()
    clock = FakeClock()
    controller = PowerController(
        config=config,
        event_bus=bus,
        leds={},
        adc=adc,
        adc_config=adc_config,
        clock=clock,
    )
    received: list[ShutdownRequested] = []
    bus.subscribe(ShutdownRequested, received.append)

    for _ in range(_BATTERY_WINDOW_SIZE * 2):
        controller.check_power_status()
        clock.advance(config.adc.battery_read_interval)

    assert controller.battery_is_low is False
    assert received == []


def test_power_button_countdown() -> None:
    bus = EventBus()
    controller = PowerController(config=Config(debug_mode=True), event_bus=bus, leds={})
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
    controller = PowerController(config=Config(debug_mode=True), event_bus=bus, leds={})
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
    controller = PowerController(
        config=Config(debug_mode=False), event_bus=bus, leds={}
    )
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
    controller = PowerController(
        config=Config(debug_mode=False), event_bus=bus, leds={}
    )
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
