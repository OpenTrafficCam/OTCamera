from typing import Tuple, Union

from picamerax import Color, PiCamera

from OTCamera import config
from OTCamera.domain.camera import Camera, H264Level, H264Profile, VideoFormat
from OTCamera.helpers import log


class PiCameraX(Camera):

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

    def __init__(
        self,
        picamera: PiCamera,
        frame_rate: int = config.FPS,
        resolution: tuple[int, int] = config.RESOLUTION,
        exposure_mode: str = config.EXPOSURE_MODE,
        awb_mode: str = config.AWB_MODE,
        drc_strength: str = config.DRC_STRENGTH,
        rotation: int = config.ROTATION,
        meter_mode: str = config.METER_MODE,
        annotation_background_color: Union[Color, None] = Color("black"),
    ) -> None:
        """
        The PiCamera wrapper providing functionality such as starting or stopping
        a recording, capturing a preview image, or closing the camera

        Args:
            frame_rate (int): The frame rate. Defaults to config.FPS.
            resolution (Tuple[int, int]): The resolution. Defaults to
                config.RESOLUTION.
            exposure_mode (str): The exposure mode. Defaults to
                config.EXPOSURE_MODE.
            awb_mode (str): The awb mode. Defaults to config.AWB_MODE.
            drc_strength (str): The DRC strength. Defaults to
                config.DRC_STRENGTH.
            rotation (int): The image rotation. Defaults to config.ROTATION.
            meter_mode (str): The meter mode. Defaults to config.METER_MODE.
            annotation_background_color (Color): The text annotation
                background color. Defaults to Color("black").
        """
        self._picamera = picamera
        self._frame_rate = frame_rate
        self._resolution = resolution
        self._exposure_mode = exposure_mode
        self._awb_mode = awb_mode
        self._drc_strength = drc_strength
        self._rotation = rotation
        self._meter_mode = meter_mode
        self._annotation_background_color = annotation_background_color

        log.write("Initializing Camera", level=log.LogLevel.DEBUG)
        self._setup_picamera()
        log.write("Camera initialized", log.LogLevel.DEBUG)

    def _setup_picamera(self) -> None:
        self.set_frame_rate(self._frame_rate)
        self.set_resolution(self._resolution)
        self.set_exposure_mode(self._exposure_mode)
        self.set_awb_mode(self._awb_mode)
        self.set_drc_strength(self._drc_strength)
        self.set_rotation(self._rotation)
        self.set_meter_mode(self._meter_mode)
        self.set_annotation_background_color(self._annotation_background_color)

    @property
    def is_recording(self) -> bool:
        return self._picamera.recording

    def start_recording(
        self,
        save_file: str,
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
    ) -> None:
        self._picamera.capture(
            output=save_file,
            format=image_format,
            resize=resolution,
            use_video_port=True,
        )

    def wait_recording(self, timeout: Union[int, float]) -> None:
        self._picamera.wait_recording(timeout=timeout)

    def split_recording(self, save_path: str) -> None:
        self._picamera.split_recording(output=save_path)

    def stop_recording(self) -> None:
        self._picamera.stop_recording()

    def close(self) -> None:
        self._picamera.close()

    def reinitialize(self) -> None:
        self.close()
        self._picamera = PiCamera()
        self._setup_picamera()

    def set_annotation_text(self, value: str) -> None:
        self._picamera.annotate_text = value

    def set_annotation_background_color(self, value: Color) -> None:
        self._picamera.annotate_background = value

    def set_frame_rate(self, value: int) -> None:
        self._frame_rate = value
        self._picamera.framerate = value

    def set_resolution(self, value: tuple[int, int]) -> None:
        self._resolution = value
        self._picamera.resolution = value

    def set_exposure_mode(self, value: str) -> None:
        self._exposure_mode = value
        self._picamera.exposure_mode = value

    def set_awb_mode(self, value: str) -> None:
        self._awb_mode = value
        self._picamera.awb_mode = value

    def set_drc_strength(self, value: str) -> None:
        self._drc_strength = value
        self._picamera.drc_strength = value

    def set_rotation(self, value: int) -> None:
        self._rotation = value
        self._picamera.rotation = value

    def set_meter_mode(self, value: str) -> None:
        self._meter_mode = value
        self._picamera.meter_mode = value
