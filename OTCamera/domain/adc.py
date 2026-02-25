from abc import ABC, abstractmethod


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
