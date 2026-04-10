
class OTCameraError(Exception):
    """Base exception for OTCamera."""
    pass


class UploadUnavailableError(OTCameraError):
    """Raised when an upload backend is not available."""
    pass