import smbus2

from OTCamera.domain.adc import ADC


class TLA2024(ADC):
    """TLA2024 4-channel ADC implementation using I2C/smbus2.

    The TLA2024 is a 12-bit ADC with 4 single-ended input channels.
    """

    # Register addresses
    _REG_CONVERSION = 0x00
    _REG_CONFIG = 0x01

    # Configuration register bits
    _CONFIG_OS_SINGLE = 0x8000  # Start single conversion
    _CONFIG_MUX_OFFSET = 12  # MUX bits start at bit 12
    _CONFIG_PGA_4_096V = 0x0200  # FSR = ±4.096V
    _CONFIG_MODE_SINGLE = 0x0100  # Single-shot mode
    _CONFIG_DR_1600SPS = 0x0080  # 1600 samples per second
    _CONFIG_RESERVED = 0x0003  # Reserved bits, must be set

    # Channel to MUX configuration mapping (single-ended inputs)
    _MUX_CHANNEL = {
        0: 0x4,  # AIN0 to GND
        1: 0x5,  # AIN1 to GND
        2: 0x6,  # AIN2 to GND
        3: 0x7,  # AIN3 to GND
    }

    def __init__(self, i2c_address: int = 0x48, fsr: float = 4.096) -> None:
        """Initialize the TLA2024 ADC.

        Args:
            i2c_address: I2C address of the TLA2024 (default 0x48).
            fsr: Full scale range in volts (default ±4.096V).
        """
        self._address = i2c_address
        self._fsr = fsr
        self._bus = smbus2.SMBus(1)

    @property
    def channels(self) -> int:
        """Return the number of available channels.

        Returns:
            The number of ADC channels (4 for TLA2024).
        """
        return 4

    def get_voltage(self, channel: int) -> float:
        """Read voltage from specified channel.

        Args:
            channel: The ADC channel number (0-3).

        Returns:
            The measured voltage in volts.

        Raises:
            ValueError: If channel is not in range 0-3.
        """
        if channel not in self._MUX_CHANNEL:
            raise ValueError(f"Invalid channel {channel}. Must be 0-3.")

        # Build configuration register value
        config = (
            self._CONFIG_OS_SINGLE
            | (self._MUX_CHANNEL[channel] << self._CONFIG_MUX_OFFSET)
            | self._CONFIG_PGA_4_096V
            | self._CONFIG_MODE_SINGLE
            | self._CONFIG_DR_1600SPS
            | self._CONFIG_RESERVED
        )

        # Write configuration (big-endian)
        config_bytes = [(config >> 8) & 0xFF, config & 0xFF]
        self._bus.write_i2c_block_data(self._address, self._REG_CONFIG, config_bytes)

        # Wait for conversion to complete by polling OS bit
        while True:
            result = self._bus.read_i2c_block_data(self._address, self._REG_CONFIG, 2)
            if result[0] & 0x80:  # OS bit set means conversion complete
                break

        # Read conversion result (big-endian, 12-bit left-aligned in 16-bit register)
        data = self._bus.read_i2c_block_data(self._address, self._REG_CONVERSION, 2)
        raw_value = (data[0] << 8) | data[1]

        # TLA2024 returns 12-bit value left-aligned, shift right by 4
        raw_value = raw_value >> 4

        # Convert to voltage
        # 12-bit signed two's complement: positive range is 0 to 2047 (2^11 steps)
        # FSR is ±4.096V, so single-ended range is 0 to +4.096V
        voltage = (raw_value / 2048.0) * self._fsr

        return voltage
