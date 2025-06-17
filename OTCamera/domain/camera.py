from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, Tuple

H264Profile = Literal["baseline", "main", "high", "constrained"]
H264Level = Literal[
    "1",
    "1.0",
    "1b",
    "1.1",
    "1.2",
    "1.3",
    "2",
    "2.0",
    "2.1",
    "2.2",
    "3",
    "3.0",
    "3.1",
    "3.2",
    "4",
    "4.0",
    "4.1",
    "4.2",
]
VideoFormat = Literal["h264", "mjpeg", "yuv", "rgb", "rgba", "bgr", "bgra"]
"""
h264: Write an H.264 video stream
mjpeg: Write an M-JPEG video stream
yuv: Write the raw video data to a file in YUV420 format
rgb: Write the raw video data to a file in 24-bit RGB format
rgba: Write the raw video data to a file in 32-bit RGBA format
bgr: Write the raw video data to a file in 24-bit BGR format
bgra: Write the raw video data to a file in 32-bit BGRA format
"""


class Camera(ABC):

    @property
    @abstractmethod
    def is_recording(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def framerate(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def resolution(self) -> Tuple[int, int]:
        raise NotImplementedError

    @property
    @abstractmethod
    def exposure_mode(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def awb_mode(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def drc_strength(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def rotation(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def meter_mode(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def start_recording(
        self,
        save_file: Path,
        video_format: VideoFormat,
        resolution: tuple[int, int],
        bitrate: int,
        h264_profile: H264Profile,
        h264_level: H264Level,
        h264_quality: int,
    ) -> None:
        """Start video recording.

        Args:
            save_file (Path): Save location of the video file.
            video_format (VideoFormat): Video format used for recording.
            resolution (tuple[int, int]): Resolution of the saved video file.
            bitrate (int): Bitrate at which the video will be encoded. The maximum
                value depends on the selected H.264 leven and profile. Bitrate 0
                indicates the encoder should not use bitrate control.
            h264_profile (H264Profile): H.264 profile used for encoding. Possible values
                are "baseline", "main", "high", "constrained".
            h264_level (H264Level): H.264 level used for encoding. Can be any H.264
                level up to "4.2'.
            h264_quality (int): Quality of the encoded video. The value ranges from
                10 and 40 where 10 is extremely high quality and 40 is extremely low
                (20-25 is usually a reasonable range for H.264 encoding).
        """
        raise NotImplementedError

    @abstractmethod
    def capture(
        self,
        save_file: str,
        image_format: str,
        resolution: tuple[int, int],
        annotation_text: str,
    ) -> None:
        """Capture a preview image of the camera."""
        raise NotImplementedError

    @abstractmethod
    def wait_recording(self, timeout: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def split_recording(self, save_path: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop_recording(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Close the camera."""
        raise NotImplementedError

    @abstractmethod
    def set_frame_rate(self, value: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_resolution(self, value: tuple[int, int]) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_exposure_mode(self, value: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_awb_mode(self, value: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_video_format(self, value: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_drc_strength(self, value: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_rotation(self, value: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_meter_mode(self, value: str) -> None:
        raise NotImplementedError
