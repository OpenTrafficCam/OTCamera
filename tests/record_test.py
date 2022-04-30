import errno
from unittest import mock
import pytest
from pathlib import Path
import shutil

from OTCamera.record import record
from OTCamera.hardware.camera import Camera


@pytest.fixture
def temp_dir(tmp_path: Path):
    tmp_tests_dir = tmp_path / "tmp_tests_dir"
    tmp_tests_dir.mkdir(exist_ok=True)
    Path(tmp_tests_dir, "file_1.txt").touch()
    Path(tmp_tests_dir, "file_2.txt").touch()
    yield tmp_tests_dir
    # shutil.rmtree(tmp_tests_dir)


@mock.patch(
    "OTCamera.record.loop", side_effect=OSError(errno.ENOSPC, "Mock ENOSPC Error")
)
def test_record_handleENOSPC(temp_dir):
    camera = Camera()
    record(camera, temp_dir)
