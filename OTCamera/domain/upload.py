"""Abstract upload interface."""

from abc import ABC, abstractmethod


class Upload(ABC):
    """Contract for uploading recorded files to external storage."""

    @abstractmethod
    def upload(self, file_path: str) -> None:
        """Upload a file.

        Implementations must raise UploadError on failure.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the upload backend is reachable."""
        raise NotImplementedError

    def close(self) -> None:
        """Release upload resources."""
