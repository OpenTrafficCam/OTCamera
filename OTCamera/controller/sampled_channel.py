"""A single ADC channel sampled on a fixed cadence, holding a window of Samples."""

import logging
from collections import deque

from OTCamera.domain.adc import ADC, ADCTimeoutError

logger = logging.getLogger(__name__)

_CONSECUTIVE_FAILURES_WARNING = 5


class SampledChannel:
    """Reads one ADC channel at most once per interval, keeping a window of Samples."""

    def __init__(
        self,
        adc: ADC,
        channel: int,
        divider_ratio: float,
        read_interval: float,
        window_size: int,
    ) -> None:
        self._adc = adc
        self._channel = channel
        self._divider_ratio = divider_ratio
        self._read_interval = read_interval
        self._samples: deque[float] = deque(maxlen=window_size)
        self._last_attempt: float | None = None
        self._consecutive_failures = 0

    @property
    def samples(self) -> tuple[float, ...]:
        """Return the currently held Samples, oldest first."""
        return tuple(self._samples)

    def sample_if_due(self, now: float) -> None:
        """Read the channel if the read interval has elapsed since the last attempt."""
        if (
            self._last_attempt is not None
            and now - self._last_attempt < self._read_interval
        ):
            return
        self._last_attempt = now
        try:
            voltage = self._adc.get_voltage(self._channel) * self._divider_ratio
        except ADCTimeoutError:
            self._consecutive_failures += 1
            if self._consecutive_failures == _CONSECUTIVE_FAILURES_WARNING:
                logger.warning(
                    "ADC channel %d: %d consecutive read failures",
                    self._channel,
                    self._consecutive_failures,
                )
            return
        self._consecutive_failures = 0
        self._samples.append(voltage)
        logger.debug("ADC channel %d sample: %.3f V", self._channel, voltage)
