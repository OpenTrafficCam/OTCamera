"""Power monitoring and system control."""

import logging
import time
from collections.abc import Callable
from datetime import datetime as dt
from datetime import timedelta
from subprocess import call

from OTCamera.config import Config
from OTCamera.controller.sampled_channel import SampledAdcChannel
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

_POWER_SHUTDOWN_DELAY = 5
_BATTERY_WINDOW_SIZE = 5


def _battery_estimate(samples: tuple[float, ...]) -> float | None:
    """Return the highest Voltage in a full window of Samples, else None.

    The battery counts as low only when every Sample in the window is below the
    threshold, which the highest Sample decides on its own. A partly filled
    window yields no verdict.
    """
    if len(samples) < _BATTERY_WINDOW_SIZE:
        return None
    return max(samples)


class PowerController:
    """Monitors battery/USB state and handles shutdown requests."""

    def __init__(
        self,
        *,
        config: Config,
        event_bus: EventBus,
        leds: dict[str, LED],
        adc: ADC | None = None,
        adc_config: ADCConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._adc = adc
        self._adc_config = adc_config
        self._clock = clock
        self._external_power_connected = False
        self._battery_is_low = False
        self._power_off_time: dt | None = None
        self._battery_channel: SampledAdcChannel | None = None

        event_bus.subscribe(ButtonPressed, self._on_button_pressed)
        event_bus.subscribe(ButtonReleased, self._on_button_released)

        if adc is not None and adc_config is not None:
            self._battery_channel = SampledAdcChannel(
                adc=adc,
                channel=adc_config.channel_battery,
                divider_ratio=adc_config.divider_ratio_battery,
                read_interval=config.adc.battery_read_interval,
                window_size=_BATTERY_WINDOW_SIZE,
            )
            try:
                self._external_power_connected = self.is_external_power
            except ADCTimeoutError:
                logger.warning(
                    "ADC timeout during initialization; assuming no external power",
                )

    @property
    def has_adc(self) -> bool:
        """Return whether ADC support is active."""
        return self._adc is not None and self._adc_config is not None

    @property
    def battery_is_low(self) -> bool:
        """Return whether a low-battery state was already latched."""
        return self._battery_is_low

    @property
    def is_external_power(self) -> bool:
        """Return whether external power is connected."""
        if self._adc is None or self._adc_config is None:
            return False
        voltage = self._adc.get_voltage(self._adc_config.channel_usb)
        return (
            voltage * self._adc_config.divider_ratio_usb
            > self._config.adc.threshold_external_power
        )

    @property
    def external_power_connected(self) -> bool:
        """Return the last known external-power state."""
        return self._external_power_connected

    @property
    def shutdown_active(self) -> bool:
        """Return whether a shutdown countdown is active."""
        return self._power_off_time is not None

    def check_power_status(self) -> None:
        """Check power state and publish power-related events."""
        if (
            self._adc is None
            or self._adc_config is None
            or self._battery_channel is None
        ):
            return

        self._battery_channel.sample_if_due(self._clock())

        samples = self._battery_channel.samples
        estimate = _battery_estimate(samples)
        if (
            estimate is not None
            and estimate < self._config.adc.threshold_low_battery
            and not self._battery_is_low
        ):
            self._on_low_battery(estimate, len(samples))

        was_connected = self._external_power_connected
        try:
            is_connected = self.is_external_power
        except ADCTimeoutError:
            logger.warning("ADC timeout reading USB state; keeping previous state")
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
        """Trigger shutdown once the power-off countdown has elapsed."""
        if self._power_off_time is None:
            return
        if self._power_off_time + timedelta(seconds=_POWER_SHUTDOWN_DELAY) < dt.now():
            self._power_off_time = None
            self.shutdown(source="button")

    def shutdown(self, source: str = "unknown") -> None:
        """Publish a shutdown request, then continue with OS shutdown."""
        logger.info("Shutdown requested by %s", source)
        self._event_bus.publish(ShutdownRequested(source=source))

        power_led = self._leds.get("power")
        if power_led is not None:
            power_led.on()

        if not self._config.debug_mode:
            logging.shutdown()
            call(["sudo", "shutdown", "-h", "now"])

    def reboot(self) -> None:
        """Request a reboot."""
        logger.info("Rebooting")
        power_led = self._leds.get("power")
        if power_led is not None:
            power_led.blink(on_time=0.1, off_time=0.1, n=None, background=True)

        if not self._config.debug_mode:
            logging.shutdown()
            call(["sudo", "reboot"])

    def _on_button_pressed(self, event: ButtonPressed) -> None:
        """Cancel a pending shutdown when the power switch turns back on."""
        if event.name != "power":
            return
        if self._power_off_time is not None:
            self._power_off_time = None
            logger.info("Shutdown cancelled; power switch back ON")
        power_led = self._leds.get("power")
        if power_led is not None:
            blink_count = 2 if self._external_power_connected else 1
            power_led.blink(
                on_time=0.1,
                off_time=0.1,
                n=blink_count,
                background=True,
            )

    def _on_button_released(self, event: ButtonReleased) -> None:
        """Start the shutdown countdown when the power switch turns off."""
        if event.name != "power":
            return
        self._power_off_time = dt.now()
        logger.info("Power switch OFF; shutdown in %d s", _POWER_SHUTDOWN_DELAY)
        power_led = self._leds.get("power")
        if power_led is not None:
            power_led.blink(on_time=0.1, off_time=0.4, n=None, background=True)

    def _on_low_battery(self, estimate: float, sample_count: int) -> None:
        """Latch low-battery state and request shutdown."""
        self._battery_is_low = True
        logger.warning(
            "Battery low: highest sample %.2f V < threshold %.2f V (%d samples)",
            estimate,
            self._config.adc.threshold_low_battery,
            sample_count,
        )
        self._event_bus.publish(BatteryLow())
        self.shutdown(source="battery")
