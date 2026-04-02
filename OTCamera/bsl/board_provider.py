"""Board provider for the board support layer."""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from OTCamera.bsl.boards.board import Board
from OTCamera.bsl.boards.v2 import BoardV2
from OTCamera.config import Config
from OTCamera.domain.adc import ADC, ADCConfig
from OTCamera.domain.button import Button
from OTCamera.domain.led import LED

logger = logging.getLogger(__name__)

_BOARD_REGISTRY: dict[str, type] = {
    "v2": BoardV2,
}


@dataclass
class BoardComponents:
    """All hardware components provided by the board."""

    leds: dict[str, LED]
    buttons: dict[str, Button]
    adc: Optional[ADC]
    adc_config: Optional[ADCConfig]

    def close(self) -> None:
        """Close all components and continue on errors."""
        for name, led in self.leds.items():
            try:
                led.close()
            except Exception:
                logger.exception("Failed to close LED %s", name)
        for name, button in self.buttons.items():
            try:
                button.close()
            except Exception:
                logger.exception("Failed to close button %s", name)
        if self.adc is not None:
            try:
                self.adc.close()
            except Exception:
                logger.exception("Failed to close ADC")


def load_board_definition(pcb_version: str) -> Board:
    """Return the board definition for the given PCB version."""
    try:
        board_cls = _BOARD_REGISTRY[pcb_version]
    except KeyError as exc:
        raise ValueError(
            "Unknown PCB version: %r. Available: %s"
            % (pcb_version, list(_BOARD_REGISTRY.keys()))
        ) from exc
    return board_cls()


class BoardProvider:
    """Instantiate all BSL components for the configured PCB version."""

    @staticmethod
    def provide(config: Config) -> BoardComponents:
        """Create LEDs, buttons and ADC according to config."""
        board = load_board_definition(config.hardware.pcb_version)
        logger.info("Loaded board definition: PCB %s", config.hardware.pcb_version)

        leds: dict[str, LED] = {}
        buttons: dict[str, Button] = {}
        adc: Optional[ADC] = None
        adc_config: Optional[ADCConfig] = None
        created_components: list[Any] = []

        try:
            if config.hardware.use_leds or config.hardware.use_buttons:
                from gpiozero import Device
                from gpiozero.pins.lgpio import LGPIOFactory

                Device.pin_factory = LGPIOFactory()

            if config.hardware.use_leds:
                from OTCamera.bsl.led.pwm_led import PwmLed

                leds = {
                    "power": PwmLed(board.led_power_pin),
                    "recording": PwmLed(board.led_rec_pin),
                    "wifi": PwmLed(board.led_wifi_pin),
                }
                created_components.extend(leds.values())
                for led in leds.values():
                    led.off()
                logger.debug("LEDs initialized: %s", list(leds.keys()))

            if config.hardware.use_buttons:
                from OTCamera.bsl.button.gpio_button import GpioButton

                buttons = {
                    "power": GpioButton(
                        board.button_power_pin,
                        pull_up=board.button_power_pull_up,
                        hold_time=board.button_hold_time,
                    ),
                    "hour": GpioButton(
                        board.button_hour_pin,
                        pull_up=board.button_hour_pull_up,
                        hold_time=board.button_hold_time,
                    ),
                    "wifi": GpioButton(
                        board.button_wifi_pin,
                        pull_up=board.button_wifi_pull_up,
                        hold_time=board.button_hold_time,
                    ),
                }
                created_components.extend(buttons.values())
                logger.debug("Buttons initialized: %s", list(buttons.keys()))

            if config.hardware.use_adc:
                from OTCamera.bsl.adc.tla2024 import TLA2024

                adc = TLA2024(board.adc_i2c_address, board.adc_fsr)
                created_components.append(adc)
                adc_config = ADCConfig(
                    channel_usb=board.adc_channel_usb,
                    channel_battery=board.adc_channel_battery,
                    divider_ratio_usb=board.adc_divider_ratio_usb,
                    divider_ratio_battery=board.adc_divider_ratio_battery,
                )
                logger.debug("ADC initialized")
        except Exception:
            for component in created_components:
                try:
                    component.close()
                except Exception:
                    logger.exception(
                        "Failed to close component during init cleanup",
                        exc_info=True,
                    )
            raise

        return BoardComponents(
            leds=leds,
            buttons=buttons,
            adc=adc,
            adc_config=adc_config,
        )
