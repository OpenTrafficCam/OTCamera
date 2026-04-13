class OTCameraError(Exception):
    """Base exception for OTCamera."""
    pass


class UploadError(OTCameraError):
    """Raised when an upload backend cannot complete an upload."""
    pass


class BackendUnavailableError(UploadError):
    """Raised when an upload backend is not available."""
    pass
