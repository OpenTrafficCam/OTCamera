"""Abstract upload interface."""

from abc import ABC, abstractmethod


class Upload(ABC):
    """Contract for uploading recorded files to external storage."""

    @abstractmethod
    def upload(self, file_path: str) -> None:
        """Upload a file.

        Implementations must raise FileUploadError on failure and must configure
        I/O-level timeouts (e.g. socket or request timeouts) so that this
        method cannot block indefinitely. The caller runs uploads on a thread
        and has no reliable way to interrupt a hung thread from the outside.

        Args:
            file_path (Path): File path of the file that should be uploaded.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the upload backend is reachable."""
        raise NotImplementedError

    def close(self) -> None:
        """Release upload resources."""
