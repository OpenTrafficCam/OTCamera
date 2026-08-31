import pytest

from OTCamera.controller.sampled_channel import SampledAdcChannel
from OTCamera.domain.adc import ADC, ADCTimeoutError
from tests.conftest import FakeClock


class FakeADC(ADC):
    def __init__(self) -> None:
        self.voltage = 0.0
        self.raise_timeout = False
        self.read_count = 0

    @property
    def channels(self) -> int:
        return 4

    def get_voltage(self, channel: int) -> float:
        self.read_count += 1
        if self.raise_timeout:
            raise ADCTimeoutError("timeout")
        return self.voltage

    def close(self) -> None:
        return


@pytest.fixture
def adc() -> FakeADC:
    return FakeADC()


def test_empty_channel_has_no_samples(adc: FakeADC, clock: FakeClock) -> None:
    channel = SampledAdcChannel(
        adc=adc,
        channel=2,
        divider_ratio=3.0,
        read_interval=10.0,
        window_size=5,
    )

    assert channel.samples == ()


def test_first_call_is_always_due_and_scales_by_divider_ratio(
    adc: FakeADC,
    clock: FakeClock,
) -> None:
    adc.voltage = 1.1
    channel = SampledAdcChannel(
        adc=adc,
        channel=2,
        divider_ratio=3.0,
        read_interval=10.0,
        window_size=5,
    )

    channel.sample_if_due(clock())

    assert channel.samples == pytest.approx((3.3,))


def test_second_call_before_interval_elapses_does_not_read_again(
    adc: FakeADC,
    clock: FakeClock,
) -> None:
    adc.voltage = 1.1
    channel = SampledAdcChannel(
        adc=adc,
        channel=2,
        divider_ratio=3.0,
        read_interval=10.0,
        window_size=5,
    )
    channel.sample_if_due(clock())

    clock.advance(5.0)
    channel.sample_if_due(clock())

    assert adc.read_count == 1
    assert channel.samples == pytest.approx((3.3,))


def test_call_after_interval_elapses_reads_again(
    adc: FakeADC,
    clock: FakeClock,
) -> None:
    adc.voltage = 1.1
    channel = SampledAdcChannel(
        adc=adc,
        channel=2,
        divider_ratio=3.0,
        read_interval=10.0,
        window_size=5,
    )
    channel.sample_if_due(clock())

    clock.advance(10.0)
    adc.voltage = 1.2
    channel.sample_if_due(clock())

    assert adc.read_count == 2
    assert channel.samples == pytest.approx((3.3, 3.6))


def test_window_evicts_oldest_sample_beyond_window_size(
    adc: FakeADC,
    clock: FakeClock,
) -> None:
    channel = SampledAdcChannel(
        adc=adc,
        channel=2,
        divider_ratio=1.0,
        read_interval=10.0,
        window_size=3,
    )

    for i, voltage in enumerate([1.0, 2.0, 3.0, 4.0]):
        adc.voltage = voltage
        channel.sample_if_due(clock())
        clock.advance(10.0 * (i + 1))

    assert channel.samples == pytest.approx((2.0, 3.0, 4.0))


def test_timeout_appends_nothing_and_preserves_held_samples(
    adc: FakeADC,
    clock: FakeClock,
) -> None:
    adc.voltage = 1.1
    channel = SampledAdcChannel(
        adc=adc,
        channel=2,
        divider_ratio=3.0,
        read_interval=10.0,
        window_size=5,
    )
    channel.sample_if_due(clock())

    clock.advance(10.0)
    adc.raise_timeout = True
    channel.sample_if_due(clock())

    assert channel.samples == pytest.approx((3.3,))


def test_timeout_does_not_propagate(adc: FakeADC, clock: FakeClock) -> None:
    channel = SampledAdcChannel(
        adc=adc,
        channel=2,
        divider_ratio=3.0,
        read_interval=10.0,
        window_size=5,
    )
    adc.raise_timeout = True

    channel.sample_if_due(clock())

    assert channel.samples == ()


def test_every_failed_read_logs_one_warning(
    adc: FakeADC,
    clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    channel = SampledAdcChannel(
        adc=adc,
        channel=2,
        divider_ratio=3.0,
        read_interval=10.0,
        window_size=5,
    )
    adc.raise_timeout = True

    with caplog.at_level("WARNING"):
        for i in range(3):
            channel.sample_if_due(clock())
            clock.advance(10.0 * (i + 1))

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 3


def test_successful_read_logs_no_warning(
    adc: FakeADC,
    clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    adc.voltage = 1.1
    channel = SampledAdcChannel(
        adc=adc,
        channel=2,
        divider_ratio=3.0,
        read_interval=10.0,
        window_size=5,
    )

    with caplog.at_level("WARNING"):
        channel.sample_if_due(clock())

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 0
