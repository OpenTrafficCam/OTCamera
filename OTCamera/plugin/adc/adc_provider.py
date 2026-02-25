from typing import Optional

from OTCamera import config
from OTCamera.abstraction.singleton import Singleton
from OTCamera.domain.adc import ADC


class ADCProvider(Singleton):
    """Singleton provider for ADC instances.

    Returns the appropriate ADC implementation based on configuration,
    or None if ADC is not enabled.
    """

    def init(self) -> None:
        self.__actual: Optional[ADC] = None

    def provide(self) -> Optional[ADC]:
        """Provide the ADC instance.

        Returns:
            The ADC instance if ADC is enabled, None otherwise.
        """
        if not config.ADC_ENABLED:
            return None

        if self.__actual:
            return self.__actual

        from OTCamera.plugin.adc.tla2024 import TLA2024

        self.__actual = TLA2024(config.ADC_I2C_ADDRESS, config.ADC_FSR)
        return self.__actual
