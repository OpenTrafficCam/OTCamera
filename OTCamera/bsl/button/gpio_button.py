"""Button implementation using gpiozero."""

from typing import Callable

from OTCamera.domain.button import Button


class GpioButton(Button):
    """Physical GPIO switch backed by gpiozero.

    With ``pull_up=None``, ``active_state`` explicitly selects the active level.
    Otherwise, leave ``active_state=None`` to derive it from the internal pull.
    """

    def __init__(
        self,
        pin: int,
        bounce_time: float,
        pull_up: bool | None = True,
        hold_time: float = 2.0,
        active_state: bool | None = None,
    ) -> None:
        from gpiozero import Button as GpioZeroButton

        self._button = GpioZeroButton(
            pin,
            pull_up=pull_up,
            active_state=active_state,
            hold_time=hold_time,
            hold_repeat=False,
            bounce_time=bounce_time,
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
