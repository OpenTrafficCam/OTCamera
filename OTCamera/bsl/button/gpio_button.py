"""Button implementation using gpiozero."""

from typing import Callable

from OTCamera.domain.button import Button


class GpioButton(Button):
    """Physical GPIO switch backed by gpiozero."""

    def __init__(
        self,
        pin: int,
        pull_up: bool = True,
        hold_time: float = 2.0,
    ) -> None:
        from gpiozero import Button as GpioZeroButton

        self._button = GpioZeroButton(
            pin,
            pull_up=pull_up,
            hold_time=hold_time,
            hold_repeat=False,
        )

    def on_pressed(self, callback: Callable[[], None]) -> None:
        self._button.when_pressed = callback

    def on_held(self, callback: Callable[[], None]) -> None:
        self._button.when_held = callback

    def on_released(self, callback: Callable[[], None]) -> None:
        self._button.when_released = callback

    @property
    def is_pressed(self) -> bool:
        return bool(self._button.is_pressed)

    def close(self) -> None:
        self._button.close()
