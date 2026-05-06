"""Abstract upload interface."""

from abc import ABC, abstractmethod


class UploadError(Exception):
    """Raised when an upload backend cannot complete an upload."""


class Upload(ABC):
    """Contract for uploading recorded files to external storage."""

    @abstractmethod
    def upload(self, file_path: str) -> None:
        """Upload a file."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the upload backend is reachable."""
        raise NotImplementedError

    def close(self) -> None:
        """Release upload resources."""
