from typing import Optional, Tuple, Union

import cv2
from libcamera import controls
from picamera2 import MappedArray, Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

from OTCamera import config
from OTCamera.domain.camera import Camera, H264Level, H264Profile, VideoFormat
from OTCamera.helpers import log

# DRC strength to rpi.contrast CE parameters mapping.
# Each entry sets ce_enable and lo_max/hi_max which control how aggressively
# the adaptive contrast enhancement adjusts shadows and highlights.
DRC_STRENGTH_MAP = {
    "off": {"ce_enable": 0},
    "low": {"ce_enable": 1, "lo_max": 500, "hi_max": 2000},
    "medium": {"ce_enable": 1, "lo_max": 2000, "hi_max": 4000},
    "high": {"ce_enable": 1, "lo_max": 5000, "hi_max": 8000},
}


def load_tuning_with_drc(drc_strength: str) -> dict:
    """Load the camera tuning file and apply DRC-equivalent settings.

    Modifies the ``rpi.contrast`` algorithm's adaptive contrast enhancement
    to approximate the legacy picamera DRC behaviour.

    Args:
        drc_strength: One of "off", "low", "medium", "high".

    Returns:
        The modified tuning dictionary, ready to pass to ``Picamera2(tuning=...)``.
    """
    camera_info = Picamera2.global_camera_info()
    if not camera_info:
        log.write(
            "No camera detected, returning empty tuning",
            level=log.LogLevel.WARNING,
        )
        return {}
    model = camera_info[0]["Model"]
    tuning = Picamera2.load_tuning_file(model + ".json")

    params = DRC_STRENGTH_MAP.get(drc_strength)
    if params is None:
        log.write(
            f"Unknown DRC strength '{drc_strength}', defaulting to 'off'",
            level=log.LogLevel.WARNING,
        )
        return tuning

    try:
        algo = Picamera2.find_tuning_algo(tuning, "rpi.contrast")
    except RuntimeError:
        log.write(
            "rpi.contrast algorithm not found in tuning file, "
            "DRC settings cannot be applied",
            level=log.LogLevel.WARNING,
        )
        return tuning

    for key, value in params.items():
        algo[key] = value

    log.write(f"Applied DRC strength '{drc_strength}' via rpi.contrast", log.LogLevel.DEBUG)
    return tuning


# Exposure mode mappings from legacy picamera names to libcamera enums
EXPOSURE_MODE_MAP = {
    "auto": controls.AeExposureModeEnum.Normal,
    "normal": controls.AeExposureModeEnum.Normal,
    "night": controls.AeExposureModeEnum.Long,
    "nightpreview": controls.AeExposureModeEnum.Long,
    "sports": controls.AeExposureModeEnum.Short,
    "short": controls.AeExposureModeEnum.Short,
    "long": controls.AeExposureModeEnum.Long,
}

# AWB mode mappings from legacy picamera names to libcamera enums
AWB_MODE_MAP = {
    "auto": controls.AwbModeEnum.Auto,
    "incandescent": controls.AwbModeEnum.Incandescent,
    "tungsten": controls.AwbModeEnum.Tungsten,
    "fluorescent": controls.AwbModeEnum.Fluorescent,
    "indoor": controls.AwbModeEnum.Indoor,
    "daylight": controls.AwbModeEnum.Daylight,
    "cloudy": controls.AwbModeEnum.Cloudy,
    # "greyworld" requires custom ColourGains, handled separately
}

# Metering mode mappings from legacy picamera names to libcamera enums
METER_MODE_MAP = {
    "average": controls.AeMeteringModeEnum.CentreWeighted,
    "spot": controls.AeMeteringModeEnum.Spot,
    "matrix": controls.AeMeteringModeEnum.Matrix,
    "center": controls.AeMeteringModeEnum.CentreWeighted,
    "centreweighted": controls.AeMeteringModeEnum.CentreWeighted,
}

# H264 profile mappings
H264_PROFILE_MAP = {
    "baseline": "baseline",
    "main": "main",
    "high": "high",
    "constrained": "constrained",
}


class PiCamera2(Camera):

    @property
    def framerate(self) -> int:
        return self._frame_rate

    @property
    def resolution(self) -> Tuple[int, int]:
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

    def __init__(
        self,
        picam2: Picamera2,
        frame_rate: int = config.FPS,
        resolution: tuple[int, int] = config.RESOLUTION,
        video_resolution: tuple[int, int] = config.RESOLUTION_SAVED_VIDEO_FILE,
        exposure_mode: str = config.EXPOSURE_MODE,
        awb_mode: str = config.AWB_MODE,
        drc_strength: str = config.DRC_STRENGTH,
        rotation: int = config.ROTATION,
        meter_mode: str = config.METER_MODE,
    ) -> None:
        """
        PiCamera2 wrapper providing functionality for the modern libcamera-based
        camera stack on Raspberry Pi.

        Args:
            picam2 (Picamera2): The Picamera2 instance to wrap.
            frame_rate (int): The frame rate. Defaults to config.FPS.
            resolution (Tuple[int, int]): The sensor resolution. Defaults to
                config.RESOLUTION.
            video_resolution (Tuple[int, int]): The output resolution for the
                saved video file. The ISP scales from the sensor resolution to
                this size, preserving the full field of view. Defaults to
                config.RESOLUTION_SAVED_VIDEO_FILE.
            exposure_mode (str): The exposure mode. Defaults to
                config.EXPOSURE_MODE.
            awb_mode (str): The awb mode. Defaults to config.AWB_MODE.
            drc_strength (str): The DRC strength ("off", "low", "medium",
                "high"). Defaults to config.DRC_STRENGTH. Applied via the
                rpi.contrast tuning algorithm at camera creation time.
            rotation (int): The image rotation. Defaults to config.ROTATION.
            meter_mode (str): The meter mode. Defaults to config.METER_MODE.
        """
        self._picam2 = picam2
        self._frame_rate = frame_rate
        self._resolution = resolution
        self._video_resolution = video_resolution
        self._exposure_mode = exposure_mode
        self._awb_mode = awb_mode
        self._drc_strength = drc_strength
        self._rotation = rotation
        self._meter_mode = meter_mode
        self._annotation_text: str = ""
        self._is_recording: bool = False
        self._encoder: Optional[H264Encoder] = None
        self._splittable_output: Optional[object] = None

        log.write("Initializing PiCamera2", level=log.LogLevel.DEBUG)
        self._setup_picamera()
        log.write("PiCamera2 initialized", log.LogLevel.DEBUG)

    def _build_transform(self):
        """Build a libcamera Transform from the current rotation setting.

        Note: 90/270 degree rotation requires transpose support which is only
        available on Pi 5 (PiSP). On Pi 4 (VC4) only 0 and 180 are supported.
        """
        from libcamera import Transform

        if self._rotation in (90, 270):
            log.write(
                f"Rotation {self._rotation}° requires transpose support (Pi 5 only)",
                level=log.LogLevel.WARNING,
            )
        if self._rotation == 180:
            return Transform(hflip=True, vflip=True)
        elif self._rotation == 90:
            return Transform(transpose=True, vflip=True)
        elif self._rotation == 270:
            return Transform(transpose=True, hflip=True)
        return Transform()

    def _setup_picamera(self) -> None:
        video_config = self._picam2.create_video_configuration(
            main={"size": self._video_resolution},
            sensor={"output_size": self._resolution},
            transform=self._build_transform(),
        )
        self._picam2.configure(video_config)

        # Set up annotation callback
        self._picam2.pre_callback = self._apply_annotation

        # Apply initial settings
        self._apply_controls()

        # Start the camera (required before recording)
        self._picam2.start()

    def _apply_controls(self) -> None:
        """Apply camera controls for exposure, AWB, and metering modes."""
        ctrl = {}

        # Apply exposure mode
        if self._exposure_mode in EXPOSURE_MODE_MAP:
            ctrl["AeExposureMode"] = EXPOSURE_MODE_MAP[self._exposure_mode]
        else:
            log.write(
                f"Unknown exposure mode '{self._exposure_mode}', using Normal",
                level=log.LogLevel.WARNING,
            )
            ctrl["AeExposureMode"] = controls.AeExposureModeEnum.Normal

        # Apply AWB mode
        if self._awb_mode == "greyworld":
            # Greyworld requires custom colour gains
            # Typical greyworld gains for NoIR camera
            ctrl["AwbEnable"] = False
            ctrl["ColourGains"] = (1.5, 1.5)
        elif self._awb_mode in AWB_MODE_MAP:
            ctrl["AwbMode"] = AWB_MODE_MAP[self._awb_mode]
        else:
            log.write(
                f"Unknown AWB mode '{self._awb_mode}', using Auto",
                level=log.LogLevel.WARNING,
            )
            ctrl["AwbMode"] = controls.AwbModeEnum.Auto

        # Apply metering mode
        if self._meter_mode in METER_MODE_MAP:
            ctrl["AeMeteringMode"] = METER_MODE_MAP[self._meter_mode]
        else:
            log.write(
                f"Unknown metering mode '{self._meter_mode}', using CentreWeighted",
                level=log.LogLevel.WARNING,
            )
            ctrl["AeMeteringMode"] = controls.AeMeteringModeEnum.CentreWeighted

        # Apply frame rate
        frame_duration = int(1000000 / self._frame_rate)
        ctrl["FrameDurationLimits"] = (frame_duration, frame_duration)

        self._picam2.set_controls(ctrl)

    def _apply_annotation(self, request) -> None:
        """Callback to apply text annotation to video frames using OpenCV."""
        if self._annotation_text:
            with MappedArray(request, "main") as m:
                # Draw black background rectangle for text
                text = self._annotation_text
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.7
                thickness = 2
                text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
                text_x, text_y = 10, 30
                padding = 5
                cv2.rectangle(
                    m.array,
                    (text_x - padding, text_y - text_size[1] - padding),
                    (text_x + text_size[0] + padding, text_y + padding),
                    (0, 0, 0),
                    -1,
                )
                # Draw white text
                cv2.putText(
                    m.array,
                    text,
                    (text_x, text_y),
                    font,
                    font_scale,
                    (255, 255, 255),
                    thickness,
                )

    @property
    def is_recording(self) -> bool:
        return self._is_recording

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
        from picamera2.outputs import FfmpegOutput

        try:
            from picamera2.outputs import SplittableOutput
        except ImportError:
            # Fallback for older picamera2 versions without SplittableOutput
            SplittableOutput = None

        profile = H264_PROFILE_MAP.get(h264_profile, "high")

        # Create encoder with specified parameters
        # Note: bitrate=0 means use quality-based encoding
        if bitrate > 0:
            self._encoder = H264Encoder(bitrate=bitrate, profile=profile)
        else:
            self._encoder = H264Encoder(qp=h264_quality, profile=profile)

        # Use SplittableOutput if available to enable split_recording
        if SplittableOutput is not None:
            file_output = FileOutput(save_file)
            self._splittable_output = SplittableOutput(file_output)
            self._picam2.start_encoder(self._encoder, self._splittable_output)
        else:
            # Fallback: direct file output (split_recording won't work properly)
            log.write(
                "SplittableOutput not available, split_recording may not work",
                level=log.LogLevel.WARNING,
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
        """Capture a preview image while recording continues."""
        request = self._picam2.capture_request()
        try:
            request.save("main", save_file)
        finally:
            request.release()

    def wait_recording(self, timeout: Union[int, float]) -> None:
        """Wait for the specified duration while recording continues."""
        import time

        time.sleep(timeout)

    def split_recording(self, save_path: str) -> None:
        """Split the recording to a new file."""
        try:
            from picamera2.outputs import SplittableOutput
        except ImportError:
            SplittableOutput = None

        if SplittableOutput is not None and isinstance(
            self._splittable_output, SplittableOutput
        ):
            new_output = FileOutput(save_path)
            self._splittable_output.split_output(new_output)
        else:
            # Fallback: stop and restart recording
            log.write(
                "SplittableOutput not available, using stop/start for split",
                level=log.LogLevel.WARNING,
            )
            self.stop_recording()
            self.start_recording(
                save_path,
                config.VIDEO_FORMAT,
                config.RESOLUTION_SAVED_VIDEO_FILE,
                config.H264_BITRATE,
                config.H264_PROFILE,
                config.H264_LEVEL,
                config.H264_QUALITY,
            )

    def stop_recording(self) -> None:
        if self._encoder:
            self._picam2.stop_encoder(self._encoder)
            self._encoder = None
        self._splittable_output = None
        self._is_recording = False

    def close(self) -> None:
        if self._is_recording:
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
        # Note: Frame rate changes require reconfiguration
        # This would require stopping recording, which we avoid here
        ctrl = {"FrameDurationLimits": (int(1000000 / value), int(1000000 / value))}
        self._picam2.set_controls(ctrl)

    def set_resolution(self, value: tuple[int, int]) -> None:
        self._resolution = value
        # Note: Resolution changes require reconfiguration
        # which would require stopping and restarting the camera

    def set_exposure_mode(self, value: str) -> None:
        self._exposure_mode = value
        if value in EXPOSURE_MODE_MAP:
            self._picam2.set_controls({"AeExposureMode": EXPOSURE_MODE_MAP[value]})
        else:
            log.write(
                f"Unknown exposure mode '{value}'",
                level=log.LogLevel.WARNING,
            )

    def set_awb_mode(self, value: str) -> None:
        self._awb_mode = value
        if value == "greyworld":
            self._picam2.set_controls({"AwbEnable": False, "ColourGains": (1.5, 1.5)})
        elif value in AWB_MODE_MAP:
            self._picam2.set_controls({"AwbEnable": True, "AwbMode": AWB_MODE_MAP[value]})
        else:
            log.write(
                f"Unknown AWB mode '{value}'",
                level=log.LogLevel.WARNING,
            )

    def set_drc_strength(self, value: str) -> None:
        self._drc_strength = value
        log.write(
            f"DRC strength set to '{value}'. "
            "Takes effect on next reinitialize (tuning is applied at startup).",
            level=log.LogLevel.DEBUG,
        )

    def set_rotation(self, value: int) -> None:
        self._rotation = value
        log.write(
            f"Rotation set to {value}. "
            "Takes effect on next reinitialize (requires reconfiguration).",
            level=log.LogLevel.DEBUG,
        )

    def set_meter_mode(self, value: str) -> None:
        self._meter_mode = value
        if value in METER_MODE_MAP:
            self._picam2.set_controls({"AeMeteringMode": METER_MODE_MAP[value]})
        else:
            log.write(
                f"Unknown metering mode '{value}'",
                level=log.LogLevel.WARNING,
            )
