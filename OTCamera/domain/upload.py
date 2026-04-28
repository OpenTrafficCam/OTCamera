"""Abstract upload interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from OTCamera.domain.events import FileUploaded, S3FileUploaded


@dataclass
class UploadResult:
    """Information about a completed upload."""

    local_path: Path

    def to_upload_event(self) -> FileUploaded:
        ts = datetime.now(tz=timezone.utc)
        return FileUploaded(local_path=self.local_path, timestamp=ts)


@dataclass
class S3UploadResult(UploadResult):
    """S3-specific upload result."""

    bucket: str
    key: str

    def to_upload_event(self) -> S3FileUploaded:
        """Convert to an S3FileUploaded event."""

        ts = datetime.now(tz=timezone.utc)

        return S3FileUploaded(
            local_path=self.local_path,
            timestamp=ts,
            bucket=self.bucket,
            key=self.key,
        )


class Upload(ABC):
    """Contract for uploading recorded files to external storage."""

    @abstractmethod
    def upload(self, file_path: Path) -> UploadResult:
        """Upload a file.

        Implementations must raise FileUploadError on failure and must configure
        I/O-level timeouts (e.g. socket or request timeouts) so that this
        method cannot block indefinitely. The caller runs uploads on a thread
        and has no reliable way to interrupt a hung thread from the outside.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the upload backend is reachable."""
        raise NotImplementedError

    def close(self) -> None:
        """Release upload resources."""
