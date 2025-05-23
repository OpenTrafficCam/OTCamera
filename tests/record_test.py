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

import errno
import shutil
from pathlib import Path
from typing import Iterator, Union
from unittest import mock

from cv2 import VideoCapture
import pytest

from OTCamera import config
from OTCamera.hardware.camera import Camera
from OTCamera.html_updater import StatusWebsiteUpdater
from OTCamera.record import OTCamera, get_log_files_sorted
from tests.conftest import YieldFixture

LOG_FILE_1 = Path("name_1990-01-01_20-00-00.log")
LOG_FILE_2 = Path("name_1990-01-01_21-01-00.log")
LOG_FILE_3 = Path("name_1990-01-01_21-04-00.log")
LOG_FILE_WITHOUT_TIMESTAMP = Path("name_no_timestamp.log")


@pytest.fixture
def temp_dir(test_dir: Path) -> YieldFixture[Path]:
    tmp_tests_dir = test_dir / "record"
    tmp_tests_dir.mkdir(exist_ok=True)
    Path(tmp_tests_dir, "file_1.txt").touch()
    Path(tmp_tests_dir, "file_2.txt").touch()
    yield tmp_tests_dir
    shutil.rmtree(tmp_tests_dir)


@pytest.fixture
def log_files_dir(test_dir: Path) -> YieldFixture[Path]:
    log_files_dir = test_dir / "logs"
    log_files_dir.mkdir(exist_ok=True)
    Path(log_files_dir, LOG_FILE_1).touch()
    Path(log_files_dir, LOG_FILE_2).touch()
    Path(log_files_dir, LOG_FILE_3).touch()
    yield log_files_dir
    shutil.rmtree(log_files_dir)


@pytest.fixture
def html_updater() -> StatusWebsiteUpdater:
    return mock.Mock()


@pytest.fixture
def otcamera(html_updater: StatusWebsiteUpdater, temp_dir: Path) -> OTCamera:
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
) -> None:
    with pytest.raises(Exception) as e:
        # record(camera, temp_dir)
        otcamera.record()

    mock_loop.assert_called_once()
    mock_delete_old_files.assert_called_once()
    mock_execute_shutdown.assert_called_once()
    assert str(e.value).startswith("ENOSPC error handling section entered")


@pytest.mark.skip
def test_record_videoRecordedHasCorrectFrames(
    otcamera: OTCamera, test_dir: Path
) -> None:
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


def test_get_log_info(log_files_dir: Path) -> None:
    otcamera = OTCamera(Camera(), mock.Mock(), log_dir=log_files_dir)
    otcamera._log_dir = log_files_dir

    log_files = otcamera._get_num_recent_log_files(0, 2)
    assert len(log_files) == 2


def get_frame_count(video_path: Union[Path, str]) -> int:
    def manual_count(handler: VideoCapture) -> int:
        count = 0
        while True:
            _status, frame = handler.read()
            if not _status:
                break
            count += 1
        return count

    cap = VideoCapture(str(video_path))
    # Slow, inefficient but 100% accurate method

    frame_count = manual_count(cap)
    cap.release()
    return frame_count


class TestGetLogFilesSorted:
    def test_is_sorted_by_timestamp_in_filename(self) -> None:
        given = self.create_unsorted_log_files()
        actual = get_log_files_sorted(given)
        assert actual == [
            LOG_FILE_3,
            LOG_FILE_2,
            LOG_FILE_1,
            LOG_FILE_WITHOUT_TIMESTAMP,
        ]

    def create_unsorted_log_files(self) -> Iterator[Path]:
        return iter([LOG_FILE_2, LOG_FILE_WITHOUT_TIMESTAMP, LOG_FILE_1, LOG_FILE_3])
