from pathlib import Path
from typing import Tuple

from picamerax import PiCamera

from OTCamera.abstraction.singleton import Singleton
from OTCamera.domain.camera import Camera, H264Level, H264Profile, VideoFormat


class PiCameraX(Camera, Singleton):

    @property
    def framerate(self) -> int:
        return self._picamera.framerate

    @property
    def resolution(self) -> Tuple[int, int]:
        return self._picamera.resolution

    @property
    def exposure_mode(self) -> str:
        return self._picamera.exposure_mode

    @property
    def awb_mode(self) -> str:
        return self._picamera.awb_mode

    @property
    def drc_strength(self) -> str:
        return self._picamera.drc_strength

    @property
    def rotation(self) -> int:
        return self._picamera.rotation

    @property
    def meter_mode(self) -> str:
        return self._picamera.meter_mode

    def init(
        self,
        picamera: PiCamera,
        frame_rate: int,
        resolution: tuple[int, int],
        exposure_mode: str,
        awb_mode: str,
        video_format: str,
        drc_strength: str,
        rotation: int,
        meter_mode: str,
    ) -> None:
        # TODO: Change init to __init__ when removing Singleton abstract class
        self._picamera = picamera
        self._video_format = video_format

        self.set_frame_rate(frame_rate)
        self.set_resolution(resolution)
        self.set_exposure_mode(exposure_mode)
        self.set_awb_mode(awb_mode)
        self.set_video_format(video_format)
        self.set_drc_strength(drc_strength)
        self.set_rotation(rotation)
        self.set_meter_mode(meter_mode)

    @property
    def is_recording(self) -> bool:
        return self._picamera.recording

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
        self._picamera.start_recording(
            output=save_file,
            format=video_format,
            resize=resolution,
            bitrate=bitrate,
            profile=h264_profile,
            level=h264_level,
            quality=h264_quality,
        )

    def capture(
        self,
        save_file: str,
        image_format: str,
        resolution: tuple[int, int],
        annotation_text: str,
    ) -> None:
        self._picamera.capture(
            output=save_file,
            format=image_format,
            resize=resolution,
            use_video_port=True,
        )

    def wait_recording(self, timeout: int) -> None:
        self._picamera.wait_recording(timeout=timeout)

    def split_recording(self, save_path: Path) -> None:
        self._picamera.split_recording(output=save_path)

    def stop_recording(self) -> None:
        self._picamera.stop_recording()

    def close(self) -> None:
        self._picamera.close()

    def set_annotation_text(self, value: str) -> None:
        self._picamera.annotate_text = value

    def set_frame_rate(self, value: int) -> None:
        self._picamera.framerate = value

    def set_resolution(self, value: tuple[int, int]) -> None:
        self._picamera.resolution = value

    def set_exposure_mode(self, value: str) -> None:
        self._picamera.exposure_mode = value

    def set_awb_mode(self, value: str) -> None:
        self._picamera.awb_mode = value

    def set_drc_strength(self, value: str) -> None:
        self._picamera.drc_strength = value

    def set_rotation(self, value: int) -> None:
        self._picamera.rotation = value

    def set_meter_mode(self, value: str) -> None:
        self._picamera.meter_mode = value

    def set_video_format(self, value: str) -> None:
        self._video_format = value  # Usage -> start_recording
