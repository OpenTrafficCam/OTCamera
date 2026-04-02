import pytest

from OTCamera.domain.upload import Upload, UploadError


class FakeUpload(Upload):
    def __init__(self, available: bool = True) -> None:
        self._available = available
        self.uploaded_files: list[str] = []

    def upload(self, file_path: str) -> None:
        self.uploaded_files.append(file_path)

    def is_available(self) -> bool:
        return self._available


def test_upload_abc_behaviour() -> None:
    upload = FakeUpload()
    upload.upload("/tmp/video.h264")

    assert upload.uploaded_files == ["/tmp/video.h264"]
    assert upload.is_available()
    assert not FakeUpload(available=False).is_available()


def test_upload_error_is_exception() -> None:
    error = UploadError("connection failed")

    assert isinstance(error, Exception)
    assert str(error) == "connection failed"


def test_upload_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        Upload()  # type: ignore[abstract]
