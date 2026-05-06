import pytest

from OTCamera.domain.adc import ADCConfig, ADCTimeoutError


def test_adc_config_fields() -> None:
    config = ADCConfig(
        channel_usb=0,
        channel_battery=2,
        divider_ratio_usb=2.0,
        divider_ratio_battery=2.96,
    )

    assert config.channel_usb == 0
    assert config.channel_battery == 2
    assert config.divider_ratio_usb == pytest.approx(2.0)
    assert config.divider_ratio_battery == pytest.approx(2.96)


def test_adc_config_is_frozen() -> None:
    config = ADCConfig(
        channel_usb=0,
        channel_battery=2,
        divider_ratio_usb=2.0,
        divider_ratio_battery=2.96,
    )

    with pytest.raises(AttributeError):
        config.channel_usb = 1  # type: ignore[misc]


def test_adc_timeout_error() -> None:
    error = ADCTimeoutError("I2C bus timeout")

    assert isinstance(error, Exception)
    assert str(error) == "I2C bus timeout"
