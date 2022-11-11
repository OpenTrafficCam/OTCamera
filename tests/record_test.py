# Copyright (C) 2022 OpenTrafficCam Contributors
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

import errno
import shutil
from pathlib import Path
from unittest import mock

import cv2
import pytest

from OTCamera import config
from OTCamera.hardware.camera import Camera
from OTCamera.html_updater import StatusWebsiteUpdater
from OTCamera.record import OTCamera


@pytest.fixture
def temp_dir(test_dir: Path):
    tmp_tests_dir = test_dir / "record"
    tmp_tests_dir.mkdir(exist_ok=True)
    Path(tmp_tests_dir, "file_1.txt").touch()
    Path(tmp_tests_dir, "file_2.txt").touch()
    yield tmp_tests_dir
    shutil.rmtree(tmp_tests_dir)


@pytest.fixture
def log_files_dir(test_dir: Path):
    log_file_name_1 = "name_1990-01-01_20-00-00.log"
    log_file_name_2 = "name_1990-01-01_21-01-00.log"
    log_file_name_3 = "name_1990-01-01_21-04-00.log"
    log_files_dir = test_dir / "logs"
    log_files_dir.mkdir(exist_ok=True)
    Path(log_files_dir, log_file_name_1).touch()
    Path(log_files_dir, log_file_name_2).touch()
    Path(log_files_dir, log_file_name_3).touch()
    yield log_files_dir
    shutil.rmtree(log_files_dir)


@pytest.fixture
def html_updater() -> StatusWebsiteUpdater:
    return StatusWebsiteUpdater(debug_mode_on=True)


@pytest.fixture
def otcamera(html_updater: StatusWebsiteUpdater, temp_dir: Path):
    return OTCamera(camera=Camera(), html_updater=html_updater, video_dir=temp_dir)


@mock.patch.object(OTCamera, "_execute_shutdown", return_value=None)
@mock.patch.object(
    OTCamera,
    "loop",
    side_effect=OSError(errno.ENOSPC, "Mock ENOSPC Error"),
)
@mock.patch(
    "OTCamera.record.delete_old_files",
    side_effect=Exception("ENOSPC error handling section entered"),
)
def test_record_handleENOSPC(
    mock_delete_old_files: mock.MagicMock,
    mock_loop: mock.MagicMock,
    mock_execute_shutdown: mock.MagicMock,
    otcamera: OTCamera,
):
    with pytest.raises(Exception) as e:
        # record(camera, temp_dir)
        otcamera.record()

    mock_loop.assert_called_once()
    mock_delete_old_files.assert_called_once()
    mock_execute_shutdown.assert_called_once()
    assert str(e.value).startswith("ENOSPC error handling section entered")


def test_record_videoRecordedHasCorrectFrames(otcamera: OTCamera, test_dir: Path):
    config.NUM_INTERVALS = 2
    config.INTERVAL_LENGTH = 2  # in min

    video_dir = test_dir / "videos"
    video_dir.mkdir(exist_ok=True)
    config.VIDEO_DIR = str(video_dir)

    with pytest.raises(SystemExit):
        otcamera.record()

    video_paths = [
        str(p)
        for p in Path(video_dir).iterdir()
        if p.suffix == f".{config.VIDEO_FORMAT}"
    ]
    video_paths.sort()
    actual_frame_count = get_frame_count(video_paths[1])
    expected_frame_count = config.FPS * config.INTERVAL_LENGTH * 60

    assert (
        expected_frame_count <= actual_frame_count
        and actual_frame_count <= expected_frame_count + config.FPS / 2
    )


def test_get_log_info(log_files_dir: Path):
    otcamera = OTCamera(Camera(), None, log_dir=log_files_dir)
    otcamera._log_dir = log_files_dir

    log_files = otcamera._get_num_recent_log_files(0, 2)
    assert len(log_files) == 2


def get_frame_count(video_path: Path):
    def manual_count(handler):
        frames = 0
        while True:
            _status, frame = handler.read()
            if not _status:
                break
            frames += 1
        return frames

    cap = cv2.VideoCapture(str(video_path))
    # Slow, inefficient but 100% accurate method

    frames = manual_count(cap)
    cap.release()
    return frames
