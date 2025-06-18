from typing import Optional

from picamerax import PiCamera

from OTCamera import config
from OTCamera.abstraction.singleton import Singleton
from OTCamera.domain.camera import Camera
from OTCamera.plugin.camera.picamerax import PiCameraX

LEGACY = "legacy"


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
            return PiCameraX(PiCamera())
        else:
            raise ValueError(
                f"Unknown camera type: {camera_type}. "
                f"Supported camera types: '{LEGACY}']"
            )
