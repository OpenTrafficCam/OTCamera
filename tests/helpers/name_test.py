from unittest import mock


from OTCamera.helpers import name
from OTCamera import config


@mock.patch("OTCamera.helpers.name._current_dt", return_value="2022-05-18_22-00-59")
def test_log_correctFilename(mock_current_dt: mock.MagicMock):
    actual = name.log()
    expected = f"{config.VIDEO_DIR}/{config.PREFIX}_2022-05-18_22-00-59.log"
    mock_current_dt.assert_called_once()
    assert actual == expected


@mock.patch("OTCamera.helpers.name._current_dt", return_value="2022-05-18_22-00-59")
def test_video_correctFilename(mock_current_dt: mock.MagicMock):
    actual = name.video()
    expected = f"{config.VIDEO_DIR}/{config.PREFIX}_2022-05-18_22-00-59.h264"
    mock_current_dt.assert_called_once()
    assert actual == expected
