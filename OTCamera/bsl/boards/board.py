"""Board protocol.

Board definitions provide PCB-specific hardware mappings for LEDs, buttons and ADC.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Board(Protocol):
    """Structural contract for a board definition."""

    led_power_pin: int
    led_wifi_pin: int
    led_rec_pin: int

    button_power_pin: int
    button_hour_pin: int
    button_wifi_pin: int
    button_power_pull_up: bool
    button_hour_pull_up: bool
    button_wifi_pull_up: bool
    button_hold_time: float
    button_bounce_time: float

    adc_i2c_address: int
    adc_fsr: float
    adc_channel_usb: int
    adc_channel_battery: int
    adc_divider_ratio_usb: float
    adc_divider_ratio_battery: float
