"""Abstract LED interface."""

from abc import ABC, abstractmethod


class LED(ABC):
    """Models a single LED with on/off/blink/pulse capabilities."""

    @abstractmethod
    def on(self) -> None:
        """Turn the LED on."""
        raise NotImplementedError

    @abstractmethod
    def off(self) -> None:
        """Turn the LED off."""
        raise NotImplementedError

    @abstractmethod
    def blink(
        self,
        on_time: float = 0.1,
        off_time: float = 0.1,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        """Blink the LED."""
        raise NotImplementedError

    @abstractmethod
    def pulse(
        self,
        fade_in_time: float = 0.25,
        fade_out_time: float = 0.25,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        """Pulse the LED."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release LED resources."""
        raise NotImplementedError
