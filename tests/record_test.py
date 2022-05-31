import errno
import shutil
from pathlib import Path
from unittest import mock

import cv2
import pytest

from OTCamera import config
from OTCamera.hardware.camera import Camera
from OTCamera.html_updater import OTCameraHTMLUpdater
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
def html_updater() -> OTCameraHTMLUpdater:
    return OTCameraHTMLUpdater(debug_mode_on=True)


@pytest.fixture
def otcamera(html_updater: OTCameraHTMLUpdater, temp_dir: Path):
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
