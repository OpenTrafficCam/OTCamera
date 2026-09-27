"""Button implementation using gpiozero."""

from typing import Callable

from OTCamera.domain.button import Button


class GpioButton(Button):
    """Physical GPIO switch backed by gpiozero."""

    def __init__(
        self,
        pin: int,
        bounce_time: float,
        pull_up: bool | None = True,
        hold_time: float = 2.0,
    ) -> None:
        from gpiozero import Button as GpioZeroButton

        # pull_up=None disables the internal pull; gpiozero then requires an explicit
        # active_state, and rejects one when it sets the pull itself. The switches are
        # toggles with no idle position, so a high level is the active one.
        active_state = True if pull_up is None else None

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
