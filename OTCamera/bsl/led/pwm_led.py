"""LED implementation using gpiozero PWMLED."""

from typing import Optional

from OTCamera.domain.led import LED


class PwmLed(LED):
    """LED controlled via PWM on a GPIO pin."""

    def __init__(self, pin: int) -> None:
        from gpiozero import PWMLED

        self._led = PWMLED(pin)

    def on(self) -> None:
        self._led.on()

    def off(self) -> None:
        self._led.off()

    def blink(
        self,
        on_time: float = 0.1,
        off_time: float = 0.1,
        n: Optional[int] = None,
        background: bool = True,
    ) -> None:
        self._led.off()
        self._led.blink(
            on_time=on_time,
            off_time=off_time,
            n=n,
            background=background,
        )

    def pulse(
        self,
        fade_in_time: float = 0.25,
        fade_out_time: float = 0.25,
        n: Optional[int] = None,
        background: bool = True,
    ) -> None:
        self._led.off()
        self._led.pulse(
            fade_in_time=fade_in_time,
            fade_out_time=fade_out_time,
            n=n,
            background=background,
        )

    def close(self) -> None:
        self._led.close()
