"""TLA2024 4-channel ADC implementation using I2C/smbus2."""

import contextlib
import fcntl
import logging
import time
from typing import Iterator

from OTCamera.domain.adc import ADC, ADCTimeoutError

logger = logging.getLogger(__name__)

_MAX_POLL_ITERATIONS = 100

OTC_I2C_LOCKFILE = "/tmp/otc_i2c.lock"


# TODO: remove this once no longer needed
# Used to avoid timing-collisions when otc-metrics polls i2c
# at the same time.
@contextlib.contextmanager
def i2c_lock() -> Iterator[None]:
    """Lock access to i2c bus."""
    with open(OTC_I2C_LOCKFILE, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class TLA2024(ADC):
    """TLA2024 12-bit ADC with 4 single-ended input channels."""

    _REG_CONVERSION = 0x00
    _REG_CONFIG = 0x01
    _CONFIG_OS_SINGLE = 0x8000
    _CONFIG_MUX_OFFSET = 12
    _CONFIG_PGA_4_096V = 0x0200
    _CONFIG_MODE_SINGLE = 0x0100
    _CONFIG_DR_1600SPS = 0x0080
    _CONFIG_RESERVED = 0x0003

    _MUX_CHANNEL = {
        0: 0x4,
        1: 0x5,
        2: 0x6,
        3: 0x7,
    }

    def __init__(self, i2c_address: int = 0x48, fsr: float = 4.096) -> None:
        self._address = i2c_address
        self._fsr = fsr
        try:
            import smbus2

            self._bus = smbus2.SMBus(1)
        except OSError as exc:
            raise ADCTimeoutError(f"Failed to open I2C bus: {exc}") from exc

    @property
    def channels(self) -> int:
        return 4

    def get_voltage(self, channel: int) -> float:
        if channel not in self._MUX_CHANNEL:
            raise ValueError("Invalid channel %s. Must be 0-3." % channel)

        config = (
            self._CONFIG_OS_SINGLE
            | (self._MUX_CHANNEL[channel] << self._CONFIG_MUX_OFFSET)
            | self._CONFIG_PGA_4_096V
            | self._CONFIG_MODE_SINGLE
            | self._CONFIG_DR_1600SPS
            | self._CONFIG_RESERVED
        )

        try:
            config_bytes = [(config >> 8) & 0xFF, config & 0xFF]

            with i2c_lock():
                self._bus.write_i2c_block_data(
                    self._address, self._REG_CONFIG, config_bytes
                )

                for _ in range(_MAX_POLL_ITERATIONS):
                    time.sleep(0.001)
                    result = self._bus.read_i2c_block_data(
                        self._address, self._REG_CONFIG, 2
                    )
                    if result[0] & 0x80:
                        break
                else:
                    raise ADCTimeoutError(
                        "ADC conversion timeout on channel %s" % channel
                    )

                data = self._bus.read_i2c_block_data(
                    self._address, self._REG_CONVERSION, 2
                )
        except OSError as exc:
            raise ADCTimeoutError(
                "I2C error on channel %s: %s" % (channel, exc)
            ) from exc

        raw_value = ((data[0] << 8) | data[1]) >> 4
        return (raw_value / 2048.0) * self._fsr

    def close(self) -> None:
        try:
            self._bus.close()
        except Exception:
            logger.debug("Error closing I2C bus", exc_info=True)
