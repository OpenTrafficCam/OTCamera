"""Pin mappings and hardware parameters for PCB v2."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardV2:
    """Board definition for PCB v2."""

    led_power_pin: int = 11
    led_wifi_pin: int = 12
    led_rec_pin: int = 13

    button_power_pin: int = 21
    button_hour_pin: int = 20
    button_wifi_pin: int = 19
    button_power_pull_up: bool = True
    button_hour_pull_up: bool = True
    button_wifi_pull_up: bool = True
    button_hold_time: float = 2.0

    adc_i2c_address: int = 0x48
    adc_fsr: float = 4.096
    adc_channel_usb: int = 0
    adc_channel_battery: int = 2
    adc_divider_ratio_usb: float = 2.0
    adc_divider_ratio_battery: float = 1510 / 510
