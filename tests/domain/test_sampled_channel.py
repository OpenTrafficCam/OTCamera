import pytest

from OTCamera.domain.adc import ADC, ADCTimeoutError
from OTCamera.domain.sampled_channel import SampledChannel


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


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def adc() -> FakeADC:
    return FakeADC()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def test_empty_channel_has_no_samples(adc: FakeADC, clock: FakeClock) -> None:
    channel = SampledChannel(adc, 2, 3.0, 10.0, 5, clock)

    assert channel.samples == ()


def test_first_call_is_always_due_and_scales_by_divider_ratio(
    adc: FakeADC,
    clock: FakeClock,
) -> None:
    adc.voltage = 1.1
    channel = SampledChannel(adc, 2, 3.0, 10.0, 5, clock)

    channel.sample_if_due(clock())

    assert channel.samples == pytest.approx((3.3,))


def test_second_call_before_interval_elapses_does_not_read_again(
    adc: FakeADC,
    clock: FakeClock,
) -> None:
    adc.voltage = 1.1
    channel = SampledChannel(adc, 2, 3.0, 10.0, 5, clock)
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
    channel = SampledChannel(adc, 2, 3.0, 10.0, 5, clock)
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
    channel = SampledChannel(adc, 2, 1.0, 10.0, 3, clock)

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
    channel = SampledChannel(adc, 2, 3.0, 10.0, 5, clock)
    channel.sample_if_due(clock())

    clock.advance(10.0)
    adc.raise_timeout = True
    channel.sample_if_due(clock())

    assert channel.samples == pytest.approx((3.3,))


def test_timeout_does_not_propagate(adc: FakeADC, clock: FakeClock) -> None:
    channel = SampledChannel(adc, 2, 3.0, 10.0, 5, clock)
    adc.raise_timeout = True

    channel.sample_if_due(clock())

    assert channel.samples == ()


def test_five_consecutive_failures_log_exactly_one_warning(
    adc: FakeADC,
    clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    channel = SampledChannel(adc, 2, 3.0, 10.0, 5, clock)
    adc.raise_timeout = True

    with caplog.at_level("WARNING"):
        for i in range(5):
            channel.sample_if_due(clock())
            clock.advance(10.0 * (i + 1))

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1


def test_success_resets_consecutive_failure_counter(
    adc: FakeADC,
    clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    channel = SampledChannel(adc, 2, 3.0, 10.0, 5, clock)
    adc.raise_timeout = True

    for i in range(4):
        channel.sample_if_due(clock())
        clock.advance(10.0 * (i + 1))

    adc.raise_timeout = False
    channel.sample_if_due(clock())
    clock.advance(10.0)

    adc.raise_timeout = True
    with caplog.at_level("WARNING"):
        for i in range(4):
            channel.sample_if_due(clock())
            clock.advance(10.0 * (i + 1))

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 0
