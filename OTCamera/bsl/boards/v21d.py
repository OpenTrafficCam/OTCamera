"""Pin mappings and hardware parameters for PCB v21d."""

from dataclasses import dataclass

from OTCamera.bsl.boards.v20d import BoardV20d


@dataclass(frozen=True)
class BoardV21d(BoardV20d):
    """Board definition for PCB v21d.

    Same as v20d except for the following two points.

    The Pi reads the power switch on GPIO 21 (PWR_EN_FB) instead of GPIO 4,
    which is unconnected on this board.

    The hour and light switches are not fitted. Instead, a solder bridge holds
    them permanently ON. Because of a PCB bug, a bridged line reads LOW when ON,
    so both are configured active-low. If real switches are fitted, they read
    HIGH when ON as on v20d, and these two overrides must be removed.
    """

    button_power_pin: int = 21
    button_hour_active_state: bool | None = False
    button_light_active_state: bool | None = False
