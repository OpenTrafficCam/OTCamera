from pathlib import Path

import pytest

from OTCamera.domain.upload import Upload, UploadResult
from OTCamera.plugin.upload.exceptions import UploadError


class FakeUpload(Upload):
    def __init__(self, available: bool = True) -> None:
        self._available = available
        self.uploaded_files: list[Path] = []

    def upload(self, file_path: Path) -> UploadResult:
        self.uploaded_files.append(file_path)
        return UploadResult(local_path=file_path)

    def is_available(self) -> bool:
        return self._available


class FailingUpload(Upload):
    def upload(self, _file_path: Path) -> UploadResult:
        raise UploadError("upload failed")

    def is_available(self) -> bool:
        return True


def test_upload_abc_behaviour() -> None:
    upload = FakeUpload()
    upload.upload(Path("/tmp/video.h264"))

    assert upload.uploaded_files == [Path("/tmp/video.h264")]
    assert upload.is_available()
    assert not FakeUpload(available=False).is_available()


def test_upload_error_is_exception() -> None:
    error = UploadError("connection failed")

    assert isinstance(error, Exception)
    assert str(error) == "connection failed"


def test_upload_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        Upload()  # type: ignore[abstract]
