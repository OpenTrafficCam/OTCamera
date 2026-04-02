"""Provider that creates the camera backend based on config."""

import logging

from OTCamera.config import Config
from OTCamera.domain.camera import Camera

logger = logging.getLogger(__name__)


class CameraProvider:
    """Create a camera instance based on the active configuration."""

    @staticmethod
    def provide(config: Config) -> Camera:
        """Create and configure the camera backend."""
        from picamera2 import Picamera2

        from OTCamera.module.camera.picamera2 import PiCamera2, load_tuning_with_drc

        camera_config = config.camera
        tuning = load_tuning_with_drc(camera_config.drc_strength)

        try:
            picam2 = Picamera2(tuning=tuning)
        except IndexError as exc:
            raise RuntimeError(
                "No camera detected by libcamera. "
                "Check that the camera is connected and the interface is enabled."
            ) from exc

        camera = PiCamera2(
            picam2,
            frame_rate=camera_config.fps,
            resolution=camera_config.resolution,
            video_resolution=config.video.resolution,
            exposure_mode=camera_config.exposure_mode,
            awb_mode=camera_config.awb_mode,
            drc_strength=camera_config.drc_strength,
            rotation=camera_config.rotation,
            meter_mode=camera_config.meter_mode,
        )
        logger.info("Camera initialized: picamera2")
        return camera
