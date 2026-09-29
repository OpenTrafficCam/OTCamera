"""Board protocol.

Board definitions provide PCB-specific hardware mappings for LEDs, buttons and ADC.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Board(Protocol):
    """Structural contract for a board definition.

    A pin of ``None`` means the revision does not fit that part; the provider skips
    it. ``button_*_pull_up`` of ``None`` means no internal pull, for switch lines
    that config.txt configures as ``np``. Without an internal pull, set
    ``button_*_active_state`` to ``True`` for active-high or ``False`` for
    active-low. With an internal pull, leave it at ``None`` so gpiozero derives
    the active level from the pull.
    """

    led_power_pin: int
    led_wifi_pin: int
    led_rec_pin: int
    led_intrusion_pin: int | None
    led_enable_pin: int | None

    button_power_pin: int
    button_hour_pin: int
    button_wifi_pin: int
    button_light_pin: int | None
    button_power_pull_up: bool | None
    button_hour_pull_up: bool | None
    button_wifi_pull_up: bool | None
    button_light_pull_up: bool | None
    button_power_active_state: bool | None
    button_hour_active_state: bool | None
    button_wifi_active_state: bool | None
    button_light_active_state: bool | None
    button_hold_time: float
    button_bounce_time: float

    adc_i2c_address: int
    adc_i2c_bus: int
    adc_fsr: float
    adc_channel_usb: int
    adc_channel_battery: int
    adc_divider_ratio_usb: float
    adc_divider_ratio_battery: float
