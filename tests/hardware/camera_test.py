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

import sys
from types import ModuleType
from typing import Any

import pytest

from OTCamera.config import Config
from OTCamera.domain.camera import CameraClosedError
from OTCamera.module.camera.camera_provider import CameraProvider


class _FakePicamera2:
    def __init__(self, tuning: dict) -> None:
        self.tuning = tuning


class _FakeWrappedCamera:
    def __init__(self, picam2: _FakePicamera2, **kwargs: object) -> None:
        self.picam2 = picam2
        self.kwargs = kwargs

    def close(self) -> None:
        return None

    def reinitialize(self) -> None:
        return None

    def wait_recording(self, timeout: float) -> None:
        return None

    def start_recording(
        self,
        save_file: str,
        video_format: str,
        resolution: tuple[int, int],
        bitrate: int,
        h264_profile: str,
        h264_level: str,
        h264_quality: int,
    ) -> None:
        return None

    def split_recording(self, save_path: str) -> None:
        return None

    def stop_recording(self) -> None:
        return None

    def capture(
        self,
        save_file: str,
        image_format: str,
        resolution: tuple[int, int],
    ) -> None:
        return None

    @property
    def is_recording(self) -> bool:
        return False

    @property
    def framerate(self) -> int:
        return 20

    @property
    def resolution(self) -> tuple[int, int]:
        return (2304, 1296)

    @property
    def exposure_mode(self) -> str:
        return "nightpreview"

    @property
    def awb_mode(self) -> str:
        return "greyworld"

    @property
    def drc_strength(self) -> str:
        return "high"

    @property
    def rotation(self) -> int:
        return 180

    @property
    def meter_mode(self) -> str:
        return "average"

    @property
    def annotation_text(self) -> str:
        return ""

    @annotation_text.setter
    def annotation_text(self, text: str) -> None:
        return None

    def get_video_filepath(self) -> str:
        raise CameraClosedError


def test_provide_creates_picamera2_camera(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_picamera2_module: Any = ModuleType("picamera2")
    fake_picamera2_module.Picamera2 = _FakePicamera2
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    fake_wrapper_module: Any = ModuleType("OTCamera.module.camera.picamera2")
    fake_wrapper_module.PiCamera2 = _FakeWrappedCamera
    fake_wrapper_module.load_tuning_with_drc = lambda drc_strength: {
        "drc_strength": drc_strength
    }
    monkeypatch.setitem(
        sys.modules,
        "OTCamera.module.camera.picamera2",
        fake_wrapper_module,
    )

    config = Config()

    camera = CameraProvider.provide(config)

    assert isinstance(camera, _FakeWrappedCamera)
    assert camera.picam2.tuning == {"drc_strength": "high"}
    assert camera.kwargs["frame_rate"] == config.camera.fps
    assert camera.kwargs["resolution"] == config.camera.resolution
    assert camera.kwargs["video_resolution"] == config.video.resolution
    assert camera.kwargs["lens_position"] == config.camera.lens_position
