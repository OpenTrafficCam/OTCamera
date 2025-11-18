class BaseFtpError(Exception):
    """Base class for all FTP-related errors."""


class FtpTraversalError(BaseFtpError):
    """Raised when the FTP client cannot traverse to a target directory.

    This error indicates that changing directories via ``FTP.cwd`` failed while
    attempting to navigate to the directory that contains the target file.
    """


class FtpConnectionError(BaseFtpError):
    """Raised when establishing an FTPS connection fails.

    This exception wraps any underlying errors raised by ``ftplib`` during the
    TCP connection or authentication steps.
    """


class FtpDownloadError(BaseFtpError):
    """Raised when downloading a file fails."""


class FtpUploadError(BaseFtpError):
    """Raised when uploading a file fails."""


class FtpFileNotFoundError(BaseFtpError):
    """Raised when attempting to download a file that doesn't exist."""
