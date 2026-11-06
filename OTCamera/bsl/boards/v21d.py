"""Pin mappings and hardware parameters for PCB v21d."""

from dataclasses import dataclass

from OTCamera.bsl.boards.v20d import BoardV20d


@dataclass(frozen=True)
class BoardV21d(BoardV20d):
    """Board definition for PCB v21d.

    Same as v20d except for the power switch: the Pi reads it on GPIO 21
    (PWR_EN_FB) instead of GPIO 4, which is unconnected on this board.
    """

    button_power_pin: int = 21
