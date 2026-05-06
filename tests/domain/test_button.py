from collections.abc import Callable

import pytest

from OTCamera.domain.button import Button


class FakeButton(Button):
    def __init__(self) -> None:
        self._pressed = False
        self._on_pressed: list[Callable[[], None]] = []
        self._on_held: list[Callable[[], None]] = []
        self._on_released: list[Callable[[], None]] = []

    def on_pressed(self, callback: Callable[[], None]) -> None:
        self._on_pressed.append(callback)

    def on_held(self, callback: Callable[[], None]) -> None:
        self._on_held.append(callback)

    def on_released(self, callback: Callable[[], None]) -> None:
        self._on_released.append(callback)

    @property
    def is_pressed(self) -> bool:
        return self._pressed

    def close(self) -> None:
        return

    def simulate_press(self) -> None:
        self._pressed = True
        for callback in self._on_pressed:
            callback()

    def simulate_hold(self) -> None:
        for callback in self._on_held:
            callback()

    def simulate_release(self) -> None:
        self._pressed = False
        for callback in self._on_released:
            callback()


def test_button_callbacks_and_state() -> None:
    button = FakeButton()
    received: list[str] = []
    button.on_pressed(lambda: received.append("pressed"))
    button.on_held(lambda: received.append("held"))
    button.on_released(lambda: received.append("released"))

    assert not button.is_pressed
    button.simulate_press()
    assert button.is_pressed
    button.simulate_hold()
    button.simulate_release()
    assert not button.is_pressed
    assert received == ["pressed", "held", "released"]


def test_button_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        Button()  # type: ignore[abstract]
