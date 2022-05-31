from pathlib import Path
from unittest import mock

from OTCamera import config
from OTCamera.helpers import name


@mock.patch("OTCamera.helpers.name._current_dt", return_value="2022-05-18_22-00-59")
def test_log_correctFilename(mock_current_dt: mock.MagicMock):
    actual = name.log()
    expected = f"{config.VIDEO_DIR}/{config.PREFIX}_2022-05-18_22-00-59.log"
    mock_current_dt.assert_called_once()
    assert str(actual) == expected


@mock.patch("OTCamera.helpers.name._current_dt", return_value="2022-05-18_22-00-59")
def test_video_correctFilename(mock_current_dt: mock.MagicMock):
    actual = name.video()
    expected = f"{config.VIDEO_DIR}/{config.PREFIX}_2022-05-18_22-00-59.h264"
    mock_current_dt.assert_called_once()
    assert actual == expected


def test_get_date_from_log_file_parseDateCorrectly():
    timestamp = Path("path/to/otcamera01_2022-05-20_15-57-52.log")
    result_dt = name.get_date_from_log_file(timestamp)
    assert result_dt.year == 2022
    assert result_dt.month == 5
    assert result_dt.day == 20
    assert result_dt.hour == 15
    assert result_dt.minute == 57
    assert result_dt.second == 52
