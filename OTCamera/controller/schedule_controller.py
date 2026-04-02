"""Recording schedule controller."""

import logging
from datetime import datetime as dt

from OTCamera.config import Config
from OTCamera.domain.events import ButtonPressed, ButtonReleased, EventBus

logger = logging.getLogger(__name__)


class ScheduleController:
    """Determines whether recording should be active."""

    def __init__(self, config: Config, event_bus: EventBus) -> None:
        self._config = config
        self._24_7_mode = False
        self._shutdown_active = False

        event_bus.subscribe(ButtonPressed, self._on_switch_pressed)
        event_bus.subscribe(ButtonReleased, self._on_switch_released)

    @property
    def is_24_7_mode(self) -> bool:
        """Return whether the hour switch currently forces 24/7 recording."""
        return self._24_7_mode

    @property
    def shutdown_active(self) -> bool:
        """Return whether shutdown mode is active."""
        return self._shutdown_active

    def should_record(self) -> bool:
        """Return whether recording should currently be active."""
        if self._shutdown_active:
            return False
        if self._24_7_mode:
            return True

        hour = self._current_hour()
        start = self._config.recording.start_hour
        end = self._config.recording.end_hour
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def init_from_switch(self, hour_switch_on: bool) -> None:
        """Initialize the controller from the boot-time switch position."""
        self._24_7_mode = hour_switch_on
        if hour_switch_on:
            logger.info("Hour switch ON at boot; 24/7 mode enabled")

    def set_shutdown_active(self, active: bool) -> None:
        """Enable or disable shutdown mode."""
        self._shutdown_active = active

    def _current_hour(self) -> int:
        """Return the current hour."""
        return dt.now().hour

    def _on_switch_pressed(self, event: ButtonPressed) -> None:
        """Enable 24/7 mode when the hour switch is pressed."""
        if event.name != "hour":
            return
        self._24_7_mode = True
        logger.info("Hour switch ON; 24/7 mode enabled")

    def _on_switch_released(self, event: ButtonReleased) -> None:
        """Restore scheduled mode when the hour switch is released."""
        if event.name != "hour":
            return
        self._24_7_mode = False
        logger.info("Hour switch OFF; scheduled mode restored")
