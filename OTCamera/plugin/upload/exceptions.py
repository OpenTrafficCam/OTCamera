"""Exceptions for upload backends."""

from OTCamera.exceptions import OTCameraError


class UploadError(OTCameraError):
    """Raised when an upload backend cannot complete an upload."""


class FileUploadError(UploadError):
    """Raised when uploading a specific file fails.

    All upload failures are retried the same way, no matter why they failed.
    The optional fields below do not change what happens; they are there to
    describe the cause of the failure in the log.

    Attributes:
        error_code: Backend-specific failure code, when the backend reports one.
        status_code: HTTP status code, when the backend reports one.
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Initialize a new `FileUploadError`.

        Args:
            message (str): Human-readable description of the failure.
            error_code (str | None): Backend-specific failure code, if known.
            status_code (int | None): HTTP status code, if known.
        """
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class BackendUnavailableError(UploadError):
    """Raised when an upload backend is not available."""
