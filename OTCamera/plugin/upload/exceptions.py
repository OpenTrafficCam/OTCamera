"""Exceptions for upload backends."""

from OTCamera.exceptions import OTCameraError


class UploadError(OTCameraError):
    """Raised when an upload backend cannot complete an upload."""


class FileUploadError(UploadError):
    """Raised when uploading a specific file fails."""


class BackendUnavailableError(UploadError):
    """Raised when an upload backend is not available."""
