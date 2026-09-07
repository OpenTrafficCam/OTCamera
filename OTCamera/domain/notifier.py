from abc import ABC, abstractmethod

from OTCamera.domain.upload import UploadResult


class UploadPayloadFactory[T](ABC):
    """Turns an uploaded file into a notification payload."""

    @abstractmethod
    def create(self, upload: UploadResult) -> T:
        """Build and return a payload announcing the uploaded file.

        Args:
            upload (UploadResult): Where the file was stored.

        Returns:
            T: The payload to hand to a notifier.
        """
        raise NotImplementedError


class Notifier[T](ABC):
    """Abstract interface for sending a typed payload to an external system."""

    @abstractmethod
    def notify(self, payload: T) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release underlying resources."""
        raise NotImplementedError
