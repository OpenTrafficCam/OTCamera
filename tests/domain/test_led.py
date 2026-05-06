import pytest

from OTCamera.domain.led import LED


class FakeLED(LED):
    def __init__(self) -> None:
        self.state = "off"

    def on(self) -> None:
        self.state = "on"

    def off(self) -> None:
        self.state = "off"

    def blink(
        self,
        on_time: float = 0.1,
        off_time: float = 0.1,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        self.state = "blink"

    def pulse(
        self,
        fade_in_time: float = 0.25,
        fade_out_time: float = 0.25,
        n: int | None = None,
        background: bool = True,
    ) -> None:
        self.state = "pulse"

    def close(self) -> None:
        self.state = "closed"


def test_led_abc_behaviour() -> None:
    led = FakeLED()
    led.on()
    assert led.state == "on"
    led.off()
    assert led.state == "off"
    led.blink()
    assert led.state == "blink"
    led.pulse()
    assert led.state == "pulse"
    led.close()
    assert led.state == "closed"


def test_led_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        LED()  # type: ignore[abstract]
