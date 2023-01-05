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

import shutil
from pathlib import Path
from unittest import mock

import pytest

from OTCamera.helpers.errors import NoMoreFilesToDeleteError
from OTCamera.helpers.filesystem import delete_old_files


@pytest.fixture(scope="function")
def temp_dir(test_dir: Path) -> Path:
    _dir = test_dir / "filesystem"
    _dir.mkdir(exist_ok=True)
    Path(_dir, "logfile.log").touch()
    vid_1 = Path(_dir, "video_1.h264")
    vid_2 = Path(_dir, "video_2.h264")
    vid_1.touch()
    vid_2.touch()
    assert get_dir_size(_dir) == 3
    yield _dir
    shutil.rmtree(_dir)


@pytest.fixture(scope="function")
def empty_dir(test_dir: Path) -> Path:
    _dir = test_dir / "empty"
    _dir.mkdir(exist_ok=True)
    assert get_dir_size(_dir) == 0

    yield _dir
    shutil.rmtree(_dir)


@mock.patch("OTCamera.helpers.filesystem.log.breakline", return_value=None)
@mock.patch("OTCamera.helpers.filesystem.log.write", return_value=None)
@mock.patch("OTCamera.helpers.filesystem._enough_space", return_value=False)
def test_delete_old_files_noSpaceLeft_raisesNoMoreFilesToDeleteError(
    mock_enough_space: mock.MagicMock,
    mock_log_write: mock.MagicMock,
    mock_log_breakline: mock.MagicMock,
    temp_dir: Path,
) -> None:

    with pytest.raises(NoMoreFilesToDeleteError):
        delete_old_files(video_dir=temp_dir)

    mock_enough_space.assert_called()
    mock_log_write.assert_called()
    mock_log_breakline.assert_called()
    assert get_dir_size(temp_dir, ".h264") == 1
    assert get_dir_size(temp_dir, ".log") == 1
    assert get_dir_size(temp_dir) == 2


@mock.patch("OTCamera.helpers.filesystem.log.write", return_value=None)
@mock.patch("OTCamera.helpers.filesystem._enough_space", return_value=True)
def test_delete_old_files_enoughSpace_doesNotDeleteFiles(
    mock_enough_space: mock.MagicMock, mock_log_write: mock.MagicMock, temp_dir: Path
) -> None:
    delete_old_files(video_dir=temp_dir)
    mock_enough_space.assert_called_once()
    mock_log_write.assert_called()
    assert get_dir_size(temp_dir) == 3


@mock.patch("OTCamera.helpers.filesystem.log.write", return_value=None)
@mock.patch("OTCamera.helpers.filesystem._enough_space", return_value=False)
def test_delete_old_files_emptyDirAsParam_raisesNoMoreFilesToDeleteError(
    mock_enough_space: mock.MagicMock,
    mock_log_write: mock.MagicMock,
    empty_dir: Path,
) -> None:
    with pytest.raises(NoMoreFilesToDeleteError):
        delete_old_files(video_dir=empty_dir)

    mock_enough_space.assert_called_once()
    mock_log_write.assert_called()
    assert get_dir_size(empty_dir) == 0


def get_dir_size(dir_path: Path, suffix: str = None) -> int:
    assert dir_path.is_dir()
    if suffix:
        return len([f for f in dir_path.iterdir() if f.suffix == suffix])

    return len(list(dir_path.iterdir()))
