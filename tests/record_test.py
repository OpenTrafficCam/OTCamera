import errno
import shutil
from unittest import mock
import pytest
from pathlib import Path

from OTCamera.record import record
from OTCamera.hardware.camera import Camera


@pytest.fixture
def temp_dir(test_dir: Path):
    tmp_tests_dir = test_dir / "record"
    tmp_tests_dir.mkdir(exist_ok=True)
    Path(tmp_tests_dir, "file_1.txt").touch()
    Path(tmp_tests_dir, "file_2.txt").touch()
    yield tmp_tests_dir
    shutil.rmtree(tmp_tests_dir)


@mock.patch(
    "OTCamera.record.loop", side_effect=OSError(errno.ENOSPC, "Mock ENOSPC Error")
)
@mock.patch(
    "OTCamera.record.delete_old_files",
    side_effect=Exception("ENOSPC error handling section entered"),
)
def test_record_handleENOSPC(
    mock_delete_old_files: mock.MagicMock, mock_loop: mock.MagicMock, temp_dir: Path
):
    camera = Camera()
    with pytest.raises(Exception) as e:
        record(camera, temp_dir)

    mock_loop.assert_called_once()
    mock_delete_old_files.assert_called_once()
    assert str(e.value).startswith("ENOSPC error handling section entered")
