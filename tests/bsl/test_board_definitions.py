import pytest

from OTCamera.bsl.boards.board import Board
from OTCamera.bsl.boards.v2 import BoardV2


class TestBoardDefinitions:
    def test_v2_satisfies_protocol(self) -> None:
        board = BoardV2()
        assert isinstance(board, Board)
        assert board.led_power_pin >= 0
        assert board.adc_fsr > 0

    def test_v2_is_frozen(self) -> None:
        board = BoardV2()
        with pytest.raises(AttributeError):
            board.led_power_pin = 99  # type: ignore[misc]

    def test_v2_has_all_required_fields(self) -> None:
        required = [
            "led_power_pin",
            "led_wifi_pin",
            "led_rec_pin",
            "button_power_pin",
            "button_hour_pin",
            "button_wifi_pin",
            "button_power_pull_up",
            "button_hour_pull_up",
            "button_wifi_pull_up",
            "button_hold_time",
            "adc_i2c_address",
            "adc_fsr",
            "adc_channel_usb",
            "adc_channel_battery",
            "adc_divider_ratio_usb",
            "adc_divider_ratio_battery",
        ]
        board = BoardV2()
        for field_name in required:
            assert hasattr(board, field_name), "BoardV2 missing %s" % field_name
