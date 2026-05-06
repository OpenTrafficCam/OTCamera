"""Abstract button interface."""

from abc import ABC, abstractmethod
from typing import Callable


class Button(ABC):
    """Hardware button or switch with callback registration."""

    @abstractmethod
    def on_pressed(self, callback: Callable[[], None]) -> None:
        """Register a callback for the pressed edge."""
        raise NotImplementedError

    @abstractmethod
    def on_held(self, callback: Callable[[], None]) -> None:
        """Register a callback for the held event."""
        raise NotImplementedError

    @abstractmethod
    def on_released(self, callback: Callable[[], None]) -> None:
        """Register a callback for the released edge."""
        raise NotImplementedError

    @property
    @abstractmethod
    def is_pressed(self) -> bool:
        """Return whether the button is currently pressed."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release button resources."""
        raise NotImplementedError
