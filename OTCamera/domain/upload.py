"""Abstract upload interface."""

from abc import ABC, abstractmethod
from collections.abc import Callable


class Upload(ABC):
    """Contract for uploading recorded files to external storage."""

    def __init__(self, on_success: Callable[[str], None] | None = None) -> None:
        self._on_success = on_success

    def upload(self, file_path: str) -> None:
        """Upload a file and invoke the success callback."""
        self._do_upload(file_path)
        if self._on_success:
            self._on_success(file_path)

    @abstractmethod
    def _do_upload(self, file_path: str) -> None:
        """Perform the actual upload.

        Implementations must raise UploadError on failure.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the upload backend is reachable."""
        raise NotImplementedError

    def close(self) -> None:
        """Release upload resources."""
