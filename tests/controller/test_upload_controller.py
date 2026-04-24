from OTCamera.controller.upload_controller import (
    BlockingUploadController,
    ThreadedUploadController,
)
from OTCamera.domain.events import EventBus, FileUploaded, RecordingSplit
from OTCamera.domain.upload import Upload, UploadResult
from OTCamera.plugin.upload.exceptions import UploadError


class FakeUpload(Upload):
    def __init__(self) -> None:
        self.uploaded_files: list[str] = []

    def upload(self, file_path: str) -> UploadResult:
        self.uploaded_files.append(file_path)
        return UploadResult(local_path=file_path)

    def is_available(self) -> bool:
        return True


class FailingUpload(Upload):
    def upload(self, _file_path: str) -> UploadResult:
        raise UploadError("upload failed")

    def is_available(self) -> bool:
        return True


def test_blocking_controller_publishes_file_uploaded_on_success() -> None:
    bus = EventBus()
    received: list[FileUploaded] = []
    bus.subscribe(FileUploaded, received.append)
    BlockingUploadController(bus, FakeUpload())

    bus.publish(RecordingSplit(filename="/tmp/video.h264"))

    assert len(received) == 1
    assert received[0].filename == "/tmp/video.h264"


def test_blocking_controller_does_not_publish_file_uploaded_on_failure() -> None:
    bus = EventBus()
    received: list[FileUploaded] = []
    bus.subscribe(FileUploaded, received.append)
    BlockingUploadController(bus, FailingUpload())

    bus.publish(RecordingSplit(filename="/tmp/video.h264"))

    assert received == []


def test_threaded_controller_publishes_file_uploaded_on_success() -> None:
    bus = EventBus()
    received: list[FileUploaded] = []
    bus.subscribe(FileUploaded, received.append)
    controller = ThreadedUploadController(bus, FakeUpload())

    bus.publish(RecordingSplit(filename="/tmp/video.h264"))
    controller.close(wait=True)
    bus.process_pending()

    assert len(received) == 1
    assert received[0].filename == "/tmp/video.h264"


def test_threaded_controller_does_not_publish_file_uploaded_on_failure() -> None:
    bus = EventBus()
    received: list[FileUploaded] = []
    bus.subscribe(FileUploaded, received.append)
    controller = ThreadedUploadController(bus, FailingUpload())

    bus.publish(RecordingSplit(filename="/tmp/video.h264"))
    controller.close(wait=True)

    assert received == []
