from abc import ABC, abstractmethod
from typing import Any


class UploadNotifier(ABC):

    @abstractmethod
    def notify(self, payload: Any) -> None:
        raise NotImplementedError
