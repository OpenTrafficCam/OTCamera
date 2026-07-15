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
    """Manage Wi-Fi AP state based on switch events."""

    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        leds: dict[str, LED],
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._wifi_on = True
        self._switch_off_time: dt | None = None

        event_bus.subscribe(ButtonHeld, self._on_switch_held)
        event_bus.subscribe(ButtonPressed, self._on_switch_pressed)
        event_bus.subscribe(ButtonReleased, self._on_switch_released)

    @property
    def wifi_on(self) -> bool:
        """Return whether Wi-Fi is currently on."""
        return self._wifi_on

    @property
    def switch_off_time(self) -> dt | None:
        """Return the scheduled switch-off timestamp, if any."""
        return self._switch_off_time

    def init_from_switch(self, wifi_switch_on: bool) -> None:
        """Initialize the controller from the boot-time switch position."""
        if wifi_switch_on:
            self.switch_on()
            return
        self.switch_off()

    def switch_on(self) -> None:
        """Turn Wi-Fi on immediately and cancel delayed-off state."""
        self._switch_off_time = None
        if not self._wifi_on:
            if not self._config.debug_mode:
                subprocess.call(["sudo", "rfkill", "unblock", "wlan"])
            self._wifi_on = True
            logger.info("Wi-Fi on")
            self._event_bus.publish(WifiOn())

        wifi_led = self._leds.get("wifi")
        if wifi_led is not None:
            wifi_led.blink(on_time=0.1, off_time=4.9, n=None, background=True)

    def switch_off(self) -> None:
        """Turn Wi-Fi off immediately."""
        if self._wifi_on:
            if not self._config.debug_mode:
                subprocess.call(["sudo", "rfkill", "block", "wlan"])
            self._wifi_on = False
            logger.info("Wi-Fi off")
            self._event_bus.publish(WifiOff())

        wifi_led = self._leds.get("wifi")
        if wifi_led is not None:
            wifi_led.pulse(
                fade_in_time=0.25,
                fade_out_time=0.25,
                n=4,
                background=True,
            )

    def check_pending_wifi_off(self) -> None:
        """Turn Wi-Fi off after the configured delay has expired."""
        if self._switch_off_time is None or not self._wifi_on:
            return

        delay = timedelta(seconds=self._config.wifi.delay)
        if self._switch_off_time + delay < dt.now():
            self.switch_off()
            self._switch_off_time = None

    @staticmethod
    def is_wifi_enabled(device: str = "wlan0") -> bool:
        """Return whether the given Linux network device is up."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", device],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return False
        return bool(re.search("state up", result.stdout, re.IGNORECASE))

    def _on_switch_held(self, event: ButtonHeld) -> None:
        """Turn Wi-Fi on when the switch is held."""
        if event.name != "wifi":
            return
        self.switch_on()

    def _on_switch_pressed(self, event: ButtonPressed) -> None:
        """Turn Wi-Fi on when the switch is pressed."""
        if event.name != "wifi":
            return
        self.switch_on()

    def _on_switch_released(self, event: ButtonReleased) -> None:
        """Start delayed Wi-Fi shutdown when the switch is released."""
        if event.name != "wifi":
            return
        self._switch_off_time = dt.now()
        wifi_led = self._leds.get("wifi")
        if wifi_led is not None:
            wifi_led.blink(on_time=0.1, off_time=0.9, n=None, background=True)
        logger.info("Wi-Fi turning off in %d s", self._config.wifi.delay)
