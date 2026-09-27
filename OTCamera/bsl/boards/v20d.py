"""Pin mappings and hardware parameters for PCB v20d."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardV20d:
    """Board definition for PCB v20d."""

    led_power_pin: int = 11
    led_wifi_pin: int = 12
    led_rec_pin: int = 13
    led_intrusion_pin: int | None = 7
    led_enable_pin: int | None = 10

    button_power_pin: int = 4
    button_hour_pin: int = 20
    button_wifi_pin: int = 19
    button_light_pin: int | None = 16
    button_power_pull_up: bool | None = None
    button_hour_pull_up: bool | None = None
    button_wifi_pull_up: bool | None = None
    button_light_pull_up: bool | None = None
    button_hold_time: float = 2.0
    button_bounce_time: float = 0.05

    # The board wires GPIO 2/3 otherwise, so sensors and the RTC sit on the
    # bit-banged bus declared by the i2c-gpio overlay. There is no /dev/i2c-1 here.
    adc_i2c_address: int = 0x48
    adc_i2c_bus: int = 3
    adc_fsr: float = 4.096
    adc_channel_usb: int = 0
    adc_channel_battery: int = 2
    adc_divider_ratio_usb: float = 2.0
    adc_divider_ratio_battery: float = 1510 / 510
