# Copyright (C) 2023 OpenTrafficCam Contributors
# <https://github.com/OpenTrafficCam>
# <team@opentrafficcam.org>

# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A

# PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program.  If not, see <https://www.gnu.org/licenses/>.

from pathlib import Path
from unittest import mock

import pytest

from OTCamera import config
from OTCamera.helpers import name


@mock.patch("OTCamera.helpers.name._current_dt", return_value="2022-05-18_22-00-59")
def test_log_correctFilename(mock_current_dt: mock.MagicMock) -> None:
    actual = name.log()
    expected = (
        f"{config.VIDEO_DIR}/{config.PREFIX}_FR{config.FPS}_2022-05-18_22-00-59.log"
    )
    mock_current_dt.assert_called_once()
    assert str(actual) == expected


@mock.patch("OTCamera.helpers.name._current_dt", return_value="2022-05-18_22-00-59")
def test_video_correctFilename(mock_current_dt: mock.MagicMock) -> None:
    actual = name.video()
    expected = (
        f"{config.VIDEO_DIR}/{config.PREFIX}_FR{config.FPS}_2022-05-18_22-00-59.h264"
    )
    mock_current_dt.assert_called_once()
    assert actual == expected


def test_get_datetime_from_filename_correctFilenameAsParam() -> None:
    timestamp = "otcamera01_2022-05-20_15-57-52.log"
    result_dt = name.get_datetime_from_filename(timestamp)
    assert result_dt is not None
    assert result_dt.year == 2022
    assert result_dt.month == 5
    assert result_dt.day == 20
    assert result_dt.hour == 15
    assert result_dt.minute == 57
    assert result_dt.second == 52


def test_get_datetime_from_filename_correctPathAsParam() -> None:
    timestamp = Path("path/to/otcamera01_2022-05-20_15-57-52.log")
    result_dt = name.get_datetime_from_filename(timestamp)
    assert result_dt is not None
    assert result_dt.year == 2022
    assert result_dt.month == 5
    assert result_dt.day == 20
    assert result_dt.hour == 15
    assert result_dt.minute == 57
    assert result_dt.second == 52


@pytest.mark.parametrize(
    "file_name",
    [
        "fname-0000-00-00_00-00-00123123",
        "fname-13130000-00-00_00-00-00123123",
    ],
)
def test_get_datetime_from_filename_invalidDateFormatAsParam(file_name: str) -> None:
    result = name.get_datetime_from_filename(file_name)
    assert result is None


@pytest.mark.parametrize(
    "file_name",
    [
        "fname-0000-00-00_00-00-00",
        "fname-0001-01-01-50-01-00",
        "fname_0001-13-01_01-01-01",
        "fname_0001-02-31_01-01-01",
        "fname_0001-02-31_70-01-01",
    ],
)
def test_get_datetime_from_filename_invalidDateAsParam(file_name: str) -> None:
    result = name.get_datetime_from_filename(file_name)
    assert result is None


@pytest.mark.parametrize(
    "fname, expected",
    [
        ("fname_FR001_0001-01-01_01-01-01", 1),
        ("fname_FR400_-01-01_01-01-01", 400),
        ("fname_FR0_-01-01_01-01-01", 0),
        ("fname_FR0_-01-01_01-01-01", 0),
    ],
)
def test_get_fps_from_filename_validFpsAsParam(fname: str, expected: int) -> None:
    result = name.get_fps_from_filename(fname)
    assert result == expected


@pytest.mark.parametrize(
    "fname",
    [
        "fname_FR_0001-01-01_01-01-01",
        "fname_FR0001-01-01_01-01-01",
        "fname_FR_0001-01-01_01-01-01",
        "fname_FR_",
    ],
)
def test_get_fps_from_filename_invalidFilenameAsParam(fname: str) -> None:
    result = name.get_fps_from_filename(fname)
    assert result is None
