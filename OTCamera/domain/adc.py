"""Abstract ADC interface and board-specific ADC parameters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ADC(ABC):
    """Abstract base class for analog-to-digital converters.

    Provides a generic interface for reading voltage from ADC channels.
    """

    @property
    @abstractmethod
    def channels(self) -> int:
        """Return the number of available channels.

        Returns:
            The number of ADC channels.
        """
        raise NotImplementedError

    @abstractmethod
    def get_voltage(self, channel: int) -> float:
        """Read voltage from specified channel.

        Args:
            channel: The ADC channel number to read from.

        Returns:
            The measured voltage in volts.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release ADC resources."""
        raise NotImplementedError


class ADCTimeoutError(Exception):
    """Raised when the ADC cannot complete a read operation in time."""


@dataclass(frozen=True)
class ADCConfig:
    """Board-specific ADC operational parameters."""

    channel_usb: int
    channel_battery: int
    divider_ratio_usb: float
    divider_ratio_battery: float
