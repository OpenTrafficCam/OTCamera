from typing import Optional

from OTCamera import config
from OTCamera.abstraction.singleton import Singleton
from OTCamera.domain.camera import Camera

LEGACY = "legacy"
PICAMERA2 = "picamera2"


class CameraProvider(Singleton):
    def init(self) -> None:
        self.__actual: Optional[Camera] = None

    def provide(self) -> Camera:
        if self.__actual:
            return self.__actual
        self.__actual = self.__create(config.CAMERA_TYPE)
        return self.__actual

    def __create(self, camera_type: str = LEGACY) -> Camera:
        if camera_type == LEGACY:
            from picamerax import PiCamera

            from OTCamera.plugin.camera.picamerax import PiCameraX

            return PiCameraX(PiCamera())
        elif camera_type == PICAMERA2:
            from picamera2 import Picamera2

            from OTCamera.plugin.camera.picamera2 import PiCamera2

            try:
                picam2 = Picamera2()
            except IndexError:
                raise RuntimeError(
                    "No camera detected by libcamera. "
                    "Check that the camera is connected and the interface is enabled."
                ) from None
            return PiCamera2(picam2)
        else:
            raise ValueError(
                f"Unknown camera type: {camera_type}. "
                f"Supported camera types: '{LEGACY}', '{PICAMERA2}'"
            )
