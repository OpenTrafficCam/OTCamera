"""PiCamera2 wrapper for the libcamera-based camera stack."""

import logging
from dataclasses import dataclass
from time import sleep
from typing import Optional, Union

import cv2
from libcamera import controls
from picamera2 import MappedArray, Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

from OTCamera.domain.camera import Camera, H264Level, H264Profile, VideoFormat

logger = logging.getLogger(__name__)

DRC_STRENGTH_MAP = {
    "off": {"ce_enable": 0},
    "low": {"ce_enable": 1, "lo_max": 500, "hi_max": 2000},
    "medium": {"ce_enable": 1, "lo_max": 2000, "hi_max": 4000},
    "high": {"ce_enable": 1, "lo_max": 5000, "hi_max": 8000},
}

EXPOSURE_MODE_MAP = {
    "auto": controls.AeExposureModeEnum.Normal,
    "normal": controls.AeExposureModeEnum.Normal,
    "night": controls.AeExposureModeEnum.Long,
    "nightpreview": controls.AeExposureModeEnum.Long,
    "sports": controls.AeExposureModeEnum.Short,
    "short": controls.AeExposureModeEnum.Short,
    "long": controls.AeExposureModeEnum.Long,
}

AWB_MODE_MAP = {
    "auto": controls.AwbModeEnum.Auto,
    "incandescent": controls.AwbModeEnum.Incandescent,
    "tungsten": controls.AwbModeEnum.Tungsten,
    "fluorescent": controls.AwbModeEnum.Fluorescent,
    "indoor": controls.AwbModeEnum.Indoor,
    "daylight": controls.AwbModeEnum.Daylight,
    "cloudy": controls.AwbModeEnum.Cloudy,
}

METER_MODE_MAP = {
    "average": controls.AeMeteringModeEnum.CentreWeighted,
    "spot": controls.AeMeteringModeEnum.Spot,
    "matrix": controls.AeMeteringModeEnum.Matrix,
    "center": controls.AeMeteringModeEnum.CentreWeighted,
    "centreweighted": controls.AeMeteringModeEnum.CentreWeighted,
}

H264_PROFILE_MAP = {
    "baseline": "baseline",
    "main": "main",
    "high": "high",
    "constrained": "constrained",
}


@dataclass(frozen=True)
class _RecordingParams:
    """Parameters needed to recreate the current recording."""

    save_file: str
    video_format: VideoFormat
    resolution: tuple[int, int]
    bitrate: int
    h264_profile: H264Profile
    h264_level: H264Level
    h264_quality: int


def load_tuning_with_drc(drc_strength: str) -> dict:
    """Load the tuning file and apply the configured DRC strength."""
    camera_info = Picamera2.global_camera_info()
    if not camera_info:
        logger.warning("No camera detected, returning empty tuning")
        return {}

    model = camera_info[0]["Model"]
    tuning = Picamera2.load_tuning_file(model + ".json")

    params = DRC_STRENGTH_MAP.get(drc_strength)
    if params is None:
        logger.warning("Unknown DRC strength '%s', defaulting to 'off'", drc_strength)
        return tuning

    try:
        algo = Picamera2.find_tuning_algo(tuning, "rpi.contrast")
    except RuntimeError:
        logger.warning(
            "rpi.contrast algorithm not found in tuning file; "
            "DRC settings cannot be applied"
        )
        return tuning

    for key, value in params.items():
        algo[key] = value

    logger.debug("Applied DRC strength '%s' via rpi.contrast", drc_strength)
    return tuning


class PiCamera2(Camera):
    """Camera wrapper providing video recording and preview capture."""

    def __init__(
        self,
        picam2: Picamera2,
        frame_rate: int,
        resolution: tuple[int, int],
        video_resolution: tuple[int, int],
        exposure_mode: str,
        awb_mode: str,
        drc_strength: str,
        rotation: int,
        meter_mode: str,
    ) -> None:
        self._picam2 = picam2
        self._frame_rate = frame_rate
        self._resolution = resolution
        self._video_resolution = video_resolution
        self._exposure_mode = exposure_mode
        self._awb_mode = awb_mode
        self._drc_strength = drc_strength
        self._rotation = rotation
        self._meter_mode = meter_mode
        self._annotation_text = ""
        self._is_recording = False
        self._encoder: Optional[H264Encoder] = None
        self._splittable_output: Optional[object] = None
        self._recording_params: _RecordingParams | None = None

        logger.debug("Initializing PiCamera2")
        self._setup_picamera()
        logger.debug("PiCamera2 initialized")

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def framerate(self) -> int:
        return self._frame_rate

    @property
    def resolution(self) -> tuple[int, int]:
        return self._resolution

    @property
    def exposure_mode(self) -> str:
        return self._exposure_mode

    @property
    def awb_mode(self) -> str:
        return self._awb_mode

    @property
    def drc_strength(self) -> str:
        return self._drc_strength

    @property
    def rotation(self) -> int:
        return self._rotation

    @property
    def meter_mode(self) -> str:
        return self._meter_mode

    def _setup_picamera(self) -> None:
        video_config = self._picam2.create_video_configuration(
            main={"size": self._video_resolution},
            sensor={"output_size": self._resolution},
            transform=self._build_transform(),
        )
        self._picam2.configure(video_config)
        self._picam2.pre_callback = self._apply_annotation
        self._apply_controls()
        self._picam2.start()

    def _build_transform(self) -> object:
        """Build a libcamera Transform from the current rotation setting."""
        from libcamera import Transform

        if self._rotation in (90, 270):
            logger.warning(
                "Rotation %d degrees requires transpose support (Pi 5 only)",
                self._rotation,
            )
        if self._rotation == 180:
            return Transform(hflip=True, vflip=True)
        if self._rotation == 90:
            return Transform(transpose=True, vflip=True)
        if self._rotation == 270:
            return Transform(transpose=True, hflip=True)
        return Transform()

    def _apply_controls(self) -> None:
        """Apply exposure, AWB, metering and frame-rate limits."""
        ctrl: dict[str, object] = {}

        if self._exposure_mode in EXPOSURE_MODE_MAP:
            ctrl["AeExposureMode"] = EXPOSURE_MODE_MAP[self._exposure_mode]
        else:
            logger.warning(
                "Unknown exposure mode '%s', using Normal",
                self._exposure_mode,
            )
            ctrl["AeExposureMode"] = controls.AeExposureModeEnum.Normal

        if self._awb_mode == "greyworld":
            ctrl["AwbEnable"] = False
            ctrl["ColourGains"] = (1.5, 1.5)
        elif self._awb_mode in AWB_MODE_MAP:
            ctrl["AwbMode"] = AWB_MODE_MAP[self._awb_mode]
        else:
            logger.warning("Unknown AWB mode '%s', using Auto", self._awb_mode)
            ctrl["AwbMode"] = controls.AwbModeEnum.Auto

        if self._meter_mode in METER_MODE_MAP:
            ctrl["AeMeteringMode"] = METER_MODE_MAP[self._meter_mode]
        else:
            logger.warning(
                "Unknown metering mode '%s', using CentreWeighted",
                self._meter_mode,
            )
            ctrl["AeMeteringMode"] = controls.AeMeteringModeEnum.CentreWeighted

        frame_duration = int(1_000_000 / self._frame_rate)
        ctrl["FrameDurationLimits"] = (100, frame_duration)

        self._picam2.set_controls(ctrl)

    def _apply_annotation(self, request: object) -> None:
        """Apply the current annotation text to the preview frame."""
        if not self._annotation_text:
            return
        with MappedArray(request, "main") as mapped_array:
            text = self._annotation_text
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            thickness = 2
            text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
            text_x, text_y = 10, 30
            padding = 5
            cv2.rectangle(
                mapped_array.array,
                (text_x - padding, text_y - text_size[1] - padding),
                (text_x + text_size[0] + padding, text_y + padding),
                (0, 0, 0),
                -1,
            )
            cv2.putText(
                mapped_array.array,
                text,
                (text_x, text_y),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
            )

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
        self._recording_params = _RecordingParams(
            save_file=save_file,
            video_format=video_format,
            resolution=resolution,
            bitrate=bitrate,
            h264_profile=h264_profile,
            h264_level=h264_level,
            h264_quality=h264_quality,
        )

        profile = H264_PROFILE_MAP.get(h264_profile, "high")
        if bitrate > 0:
            self._encoder = H264Encoder(
                bitrate=bitrate, profile=profile
            )
        else:
            self._encoder = H264Encoder(
                qp=h264_quality, profile=profile
            )

        try:
            from picamera2.outputs import SplittableOutput
        except ImportError:
            SplittableOutput = None

        if SplittableOutput is not None:
            file_output = FileOutput(save_file)
            self._splittable_output = SplittableOutput(file_output)
            self._picam2.start_encoder(self._encoder, self._splittable_output)
        else:
            logger.warning(
                "SplittableOutput not available, split_recording may not work"
            )
            self._splittable_output = FileOutput(save_file)
            self._picam2.start_encoder(self._encoder, self._splittable_output)

        self._is_recording = True

    def capture(
        self,
        save_file: str,
        image_format: str,
        resolution: tuple[int, int],
    ) -> None:
        request = self._picam2.capture_request()
        try:
            request.save("main", save_file)
        finally:
            request.release()

    def wait_recording(self, timeout: Union[int, float]) -> None:
        sleep(timeout)

    def split_recording(self, save_path: str) -> None:
        try:
            from picamera2.outputs import SplittableOutput
        except ImportError:
            SplittableOutput = None

        if SplittableOutput is not None and isinstance(
            self._splittable_output, SplittableOutput
        ):
            new_output = FileOutput(save_path)
            self._splittable_output.split_output(new_output)
            return

        logger.warning("SplittableOutput not available, using stop/start for split")
        self.stop_recording()
        if self._recording_params is None:
            raise RuntimeError("Recording parameters missing for split fallback")
        self.start_recording(
            save_path,
            self._recording_params.video_format,
            self._recording_params.resolution,
            self._recording_params.bitrate,
            self._recording_params.h264_profile,
            self._recording_params.h264_level,
            self._recording_params.h264_quality,
        )

    def stop_recording(self) -> None:
        if self._encoder is not None:
            self._picam2.stop_encoder(self._encoder)
            self._encoder = None
        self._splittable_output = None
        self._is_recording = False

    def close(self) -> None:
        self.stop_recording()
        self._picam2.stop()
        self._picam2.close()

    def reinitialize(self) -> None:
        self.close()
        tuning = load_tuning_with_drc(self._drc_strength)
        self._picam2 = Picamera2(tuning=tuning)
        self._setup_picamera()

    def set_annotation_text(self, value: str) -> None:
        self._annotation_text = value

    def set_frame_rate(self, value: int) -> None:
        self._frame_rate = value
        self._picam2.set_controls(
            {"FrameDurationLimits": (100, int(1_000_000 / value))}
        )

    def set_resolution(self, value: tuple[int, int]) -> None:
        self._resolution = value

    def set_exposure_mode(self, value: str) -> None:
        self._exposure_mode = value
        if value in EXPOSURE_MODE_MAP:
            self._picam2.set_controls({"AeExposureMode": EXPOSURE_MODE_MAP[value]})
        else:
            logger.warning("Unknown exposure mode '%s'", value)

    def set_awb_mode(self, value: str) -> None:
        self._awb_mode = value
        if value == "greyworld":
            self._picam2.set_controls({"AwbEnable": False, "ColourGains": (1.5, 1.5)})
        elif value in AWB_MODE_MAP:
            self._picam2.set_controls(
                {"AwbEnable": True, "AwbMode": AWB_MODE_MAP[value]}
            )
        else:
            logger.warning("Unknown AWB mode '%s'", value)

    def set_drc_strength(self, value: str) -> None:
        self._drc_strength = value
        logger.debug(
            "DRC strength set to '%s'. Takes effect on next reinitialize.", value
        )

    def set_rotation(self, value: int) -> None:
        self._rotation = value
        logger.debug("Rotation set to %d. Takes effect on next reinitialize.", value)

    def set_meter_mode(self, value: str) -> None:
        self._meter_mode = value
        if value in METER_MODE_MAP:
            self._picam2.set_controls({"AeMeteringMode": METER_MODE_MAP[value]})
        else:
            logger.warning("Unknown metering mode '%s'", value)
