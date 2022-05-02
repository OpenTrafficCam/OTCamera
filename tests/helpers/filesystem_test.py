import shutil
from unittest import mock

import pytest
from pathlib import Path

from OTCamera.helpers.filesystem import delete_old_files
from OTCamera.helpers.errors import NoMoreFilesToDeleteError


@pytest.fixture(scope="function")
def temp_dir(test_dir: Path) -> Path:
    tmp_tests_dir = test_dir / "filesystem"
    tmp_tests_dir.mkdir(exist_ok=True)
    Path(tmp_tests_dir, "logfile.log").touch()
    vid_1 = Path(tmp_tests_dir, "video_1.h264")
    vid_2 = Path(tmp_tests_dir, "video_2.h264")
    vid_1.touch()
    vid_2.touch()
    assert get_dir_size(tmp_tests_dir) == 3
    yield tmp_tests_dir
    shutil.rmtree(tmp_tests_dir)


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
