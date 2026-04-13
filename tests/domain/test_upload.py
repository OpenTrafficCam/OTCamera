import pytest

from OTCamera.domain.upload import Upload
from OTCamera.exceptions import UploadError


class FakeUpload(Upload):
    def __init__(self, available: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self._available = available
        self.uploaded_files: list[str] = []

    def _do_upload(self, file_path: str) -> None:
        self.uploaded_files.append(file_path)

    def is_available(self) -> bool:
        return self._available


class FailingUpload(Upload):
    def _do_upload(self, file_path: str) -> None:
        raise UploadError("upload failed")

    def is_available(self) -> bool:
        return True


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


def test_on_success_callback_called_after_upload() -> None:
    called_with: list[str] = []
    upload = FakeUpload(on_success=called_with.append)

    upload.upload("/tmp/video.h264")

    assert called_with == ["/tmp/video.h264"]


def test_on_success_callback_not_called_when_upload_fails() -> None:
    called_with: list[str] = []
    upload = FailingUpload(on_success=called_with.append)

    with pytest.raises(UploadError):
        upload.upload("/tmp/video.h264")

    assert called_with == []


def test_no_on_success_callback_upload_succeeds() -> None:
    upload = FakeUpload(on_success=None)

    upload.upload("/tmp/video.h264")

    assert upload.uploaded_files == ["/tmp/video.h264"]
