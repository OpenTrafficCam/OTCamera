"""Power monitoring controller using ADC.

Copyright (C) 2023 OpenTrafficCam Contributors
<https://github.com/OpenTrafficCam>
<team@opentrafficcam.org>

This program is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A

PARTICULAR PURPOSE.  See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with this
program.  If not, see <https://www.gnu.org/licenses/>.

"""

from OTCamera import config, status
from OTCamera.domain.adc import ADC
from OTCamera.helpers import log, rpi


class PowerController:
    """Controls power monitoring via ADC.

    Reads battery and USB voltages, detects low battery and external power,
    and triggers appropriate actions.
    """

    def __init__(self, adc: ADC) -> None:
        self._adc = adc
        # Initialize external power status
        status.external_power_connected = self.is_external_power
        if self.is_low_battery:
            self._on_low_battery()

    @property
    def is_low_battery(self) -> bool:
        """Check if battery voltage is below threshold."""
        return self.get_battery_voltage() < config.ADC_THRESHOLD_LOW_BATTERY

    @property
    def is_external_power(self) -> bool:
        """Check if external power (USB) is connected."""
        return self.get_usb_voltage() > config.ADC_THRESHOLD_EXTERNAL_POWER

    def get_battery_voltage(self) -> float:
        """Get actual battery voltage after applying divider ratio."""
        voltage = self._adc.get_voltage(config.ADC_CHANNEL_BATTERY)
        return voltage * config.ADC_DIVIDER_RATIO_BATTERY

    def get_usb_voltage(self) -> float:
        """Get actual USB voltage after applying divider ratio."""
        voltage = self._adc.get_voltage(config.ADC_CHANNEL_USB)
        return voltage * config.ADC_DIVIDER_RATIO_USB

    def check_power_status(self) -> None:
        """Check power status and trigger actions. Called from main loop."""
        # Check low battery
        if self.is_low_battery and not status.battery_is_low:
            self._on_low_battery()

        # Check external power changes
        was_connected = status.external_power_connected
        is_connected = self.is_external_power

        if is_connected and not was_connected:
            self._on_external_power_connected()
        elif not is_connected and was_connected:
            self._on_external_power_disconnected()

    def _on_low_battery(self) -> None:
        """Handle low battery condition."""
        status.battery_is_low = True
        log.write("Battery level is low!", log.LogLevel.WARNING)
        rpi.shutdown()

    def _on_external_power_connected(self) -> None:
        """Handle external power connection."""
        status.external_power_connected = True
        log.write("External power connected", log.LogLevel.INFO)

    def _on_external_power_disconnected(self) -> None:
        """Handle external power disconnection."""
        status.external_power_connected = False
        log.write("External power disconnected!", log.LogLevel.WARNING)
