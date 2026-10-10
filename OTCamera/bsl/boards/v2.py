"""Pin mappings and hardware parameters for PCB v2."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardV2:
    """Board definition for PCB v2."""

    led_power_pin: int = 11
    led_wifi_pin: int = 12
    led_rec_pin: int = 13
    led_intrusion_pin: int | None = None
    led_enable_pin: int | None = None

    button_power_pin: int = 21
    button_hour_pin: int = 20
    button_wifi_pin: int = 19
    button_light_pin: int | None = None
    button_power_pull_up: bool | None = True
    button_hour_pull_up: bool | None = True
    button_wifi_pull_up: bool | None = True
    button_light_pull_up: bool | None = None
    button_power_active_state: bool | None = None
    button_hour_active_state: bool | None = None
    button_wifi_active_state: bool | None = None
    button_light_active_state: bool | None = None
    button_hold_time: float = 2.0
    button_bounce_time: float = 0.05

    adc_i2c_address: int = 0x48
    adc_i2c_bus: int = 1
    adc_fsr: float = 4.096
    adc_channel_usb: int = 0
    adc_channel_battery: int = 2
    adc_divider_ratio_usb: float = 2.0
    adc_divider_ratio_battery: float = 1510 / 510
