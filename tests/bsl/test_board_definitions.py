import pytest

from OTCamera.bsl.boards.board import Board
from OTCamera.bsl.boards.v2 import BoardV2
from OTCamera.bsl.boards.v20d import BoardV20d

REQUIRED_FIELDS = [
    "led_power_pin",
    "led_wifi_pin",
    "led_rec_pin",
    "led_intrusion_pin",
    "led_enable_pin",
    "button_power_pin",
    "button_hour_pin",
    "button_wifi_pin",
    "button_light_pin",
    "button_power_pull_up",
    "button_hour_pull_up",
    "button_wifi_pull_up",
    "button_light_pull_up",
    "button_power_active_state",
    "button_hour_active_state",
    "button_wifi_active_state",
    "button_light_active_state",
    "button_hold_time",
    "button_bounce_time",
    "adc_i2c_address",
    "adc_i2c_bus",
    "adc_fsr",
    "adc_channel_usb",
    "adc_channel_battery",
    "adc_divider_ratio_usb",
    "adc_divider_ratio_battery",
]


class TestBoardDefinitions:
    @pytest.mark.parametrize("board_cls", [BoardV2, BoardV20d])
    def test_satisfies_protocol(self, board_cls: type) -> None:
        board = board_cls()
        assert isinstance(board, Board)
        assert board.led_power_pin >= 0
        assert board.adc_fsr > 0

    @pytest.mark.parametrize("board_cls", [BoardV2, BoardV20d])
    def test_is_frozen(self, board_cls: type) -> None:
        board = board_cls()
        with pytest.raises(AttributeError):
            board.led_power_pin = 99

    @pytest.mark.parametrize("board_cls", [BoardV2, BoardV20d])
    def test_has_all_required_fields(self, board_cls: type) -> None:
        board = board_cls()
        for field_name in REQUIRED_FIELDS:
            assert hasattr(board, field_name), "%s missing %s" % (
                board_cls.__name__,
                field_name,
            )

    def test_v2_has_no_optional_parts(self) -> None:
        board = BoardV2()
        assert board.led_intrusion_pin is None
        assert board.led_enable_pin is None
        assert board.button_light_pin is None
        assert board.adc_i2c_bus == 1
        assert board.button_power_pull_up is True

    def test_v20d_sits_on_the_bit_banged_bus(self) -> None:
        assert BoardV20d().adc_i2c_bus == 3

    def test_v20d_leaves_the_pull_to_config_txt(self) -> None:
        board = BoardV20d()
        assert board.button_power_pull_up is None
        assert board.button_hour_pull_up is None
        assert board.button_wifi_pull_up is None
        assert board.button_light_pull_up is None

    def test_v20d_fits_the_extra_parts(self) -> None:
        board = BoardV20d()
        assert board.led_intrusion_pin == 7
        assert board.led_enable_pin == 10
        assert board.button_light_pin == 16
