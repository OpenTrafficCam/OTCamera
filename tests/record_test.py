import errno
import shutil
from pathlib import Path
from time import sleep
from unittest import mock
import threading

import pytest

from OTCamera.hardware.camera import Camera
from OTCamera.record import record
from OTCamera import config
from OTCamera import status
from OTCamera.html_updater import OTCameraHTMLUpdater


@pytest.fixture
def temp_dir(test_dir: Path):
    tmp_tests_dir = test_dir / "record"
    tmp_tests_dir.mkdir(exist_ok=True)
    Path(tmp_tests_dir, "file_1.txt").touch()
    Path(tmp_tests_dir, "file_2.txt").touch()
    yield tmp_tests_dir
    shutil.rmtree(tmp_tests_dir)


@pytest.fixture
def html_updater() -> OTCameraHTMLUpdater:
    return OTCameraHTMLUpdater(debug_mode_on=True)


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


def test_record_videoRecordedHasCorrectFrames(test_dir: Path):
    config.PREVIEW_INTERVAL = 1
    video_dir = str(test_dir / "videos")

    def _thread_record_video(video_dir: str) -> None:
        camera = Camera()
        record(camera, video_dir)

    def _thread_sleep_and_end_recording() -> None:
        sleep(70)
        status.more_intervals = False

    thread_record = threading.Thread(target=_thread_record_video, args=(video_dir,))
    thread_end_record = threading.Thread(target=_thread_sleep_and_end_recording)

    thread_record.start()
    thread_end_record.start()

    thread_end_record.join()
    thread_record.join()
