from pathlib import Path
from time import sleep
from unittest.mock import patch

import pytest

from OTCamera.controller.backlog import Backlog
from OTCamera.controller.backlog_controller import BacklogController
from OTCamera.domain.events import EventBus, FileUploaded, RecordingSplit
from OTCamera.domain.upload import Upload, UploadResult
from OTCamera.plugin.upload.exceptions import UploadError

_GIB = 1024 * 1024 * 1024


class FakeUpload(Upload):
    def __init__(self) -> None:
        self.uploaded_files: list[Path] = []

    def upload(self, file_path: Path) -> UploadResult:
        self.uploaded_files.append(file_path)
        return UploadResult(local_path=file_path)

    def is_available(self) -> bool:
        return True


class FailingUpload(Upload):
    def __init__(self) -> None:
        self.attempted_files: list[Path] = []

    def upload(self, file_path: Path) -> UploadResult:
        self.attempted_files.append(file_path)
        raise UploadError("upload failed")

    def is_available(self) -> bool:
        return True


class FlakyUpload(Upload):
    def __init__(self, failures: int) -> None:
        self._remaining_failures = failures

    def upload(self, file_path: Path) -> UploadResult:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise UploadError("upload failed")
        return UploadResult(local_path=file_path)

    def is_available(self) -> bool:
        return True


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def backlog(tmp_path: Path) -> Backlog:
    return Backlog(video_dir=tmp_path, video_format="h264", min_free_bytes=0)


def _record_segment(
    video_dir: Path,
    timestamp: str = "2026-08-12_10-00-00",
    content: bytes = b"video",
) -> Path:
    segment = video_dir / f"cam_FR20_{timestamp}.h264"
    segment.write_bytes(content)
    return segment


def _uploaded_events(bus: EventBus) -> list[FileUploaded]:
    received: list[FileUploaded] = []
    bus.subscribe(FileUploaded, received.append)
    return received


class TestAcceptingSegments:
    def test_recording_split_moves_the_segment_into_the_backlog(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        received = _uploaded_events(bus)
        BacklogController(bus, FakeUpload(), backlog)
        segment = _record_segment(tmp_path)

        bus.publish(RecordingSplit(filename=str(segment)))

        assert (backlog.pending / segment.name).is_file()
        assert not segment.exists()
        assert received == []

    def test_recording_split_does_not_raise_when_the_backlog_fails(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        BacklogController(bus, FakeUpload(), backlog)
        segment = _record_segment(tmp_path)

        with patch.object(backlog, "add", side_effect=OSError("read-only card")):
            bus.publish(RecordingSplit(filename=str(segment)))

    def test_does_not_start_a_thread_on_construction(
        self, bus: EventBus, backlog: Backlog
    ) -> None:
        controller = BacklogController(bus, FakeUpload(), backlog)

        assert not controller.is_running


class TestSuccessfulPass:
    def test_removes_the_segment_and_enqueues_the_upload(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        received = _uploaded_events(bus)
        upload = FakeUpload()
        controller = BacklogController(bus, upload, backlog)
        segment = backlog.add(_record_segment(tmp_path))

        controller.run_once()

        assert upload.uploaded_files == [segment]
        assert not segment.exists()
        assert backlog.size() == 0
        assert received == []

        bus.process_pending()
        assert len(received) == 1
        assert received[0].local_path == segment

    def test_counts_the_upload(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        controller = BacklogController(bus, FakeUpload(), backlog)
        backlog.add(_record_segment(tmp_path))

        controller.run_once()

        assert backlog.uploaded_total == 1

    def test_drains_oldest_first(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        upload = FakeUpload()
        controller = BacklogController(bus, upload, backlog)
        newest = backlog.add(_record_segment(tmp_path, "2026-08-12_12-00-00"))
        oldest = backlog.add(_record_segment(tmp_path, "2026-08-12_10-00-00"))

        controller.run_once()
        controller.run_once()

        assert upload.uploaded_files == [oldest, newest]

    def test_an_empty_backlog_uploads_nothing(
        self, bus: EventBus, backlog: Backlog
    ) -> None:
        upload = FakeUpload()
        controller = BacklogController(bus, upload, backlog)

        controller.run_once()

        assert upload.uploaded_files == []


class TestFailingPass:
    def test_keeps_the_segment_and_publishes_nothing(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        received = _uploaded_events(bus)
        controller = BacklogController(bus, FailingUpload(), backlog)
        segment = backlog.add(_record_segment(tmp_path))

        controller.run_once()
        bus.process_pending()

        assert segment.is_file()
        assert backlog.size() == 1
        assert received == []

    def test_backs_off_from_five_seconds_by_doubling(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        controller = BacklogController(bus, FailingUpload(), backlog)
        backlog.add(_record_segment(tmp_path))

        waits = []
        for _ in range(4):
            controller.run_once()
            waits.append(controller.wait_seconds)

        assert waits == [5, 10, 20, 40]

    def test_caps_the_wait(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        controller = BacklogController(bus, FailingUpload(), backlog)
        backlog.add(_record_segment(tmp_path))

        for _ in range(20):
            controller.run_once()

        assert controller.wait_seconds == 300

    def test_retries_the_same_segment(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        upload = FailingUpload()
        controller = BacklogController(bus, upload, backlog)
        oldest = backlog.add(_record_segment(tmp_path, "2026-08-12_10-00-00"))
        backlog.add(_record_segment(tmp_path, "2026-08-12_12-00-00"))

        controller.run_once()
        controller.run_once()

        assert upload.attempted_files == [oldest, oldest]
        assert backlog.size() == 2

    def test_the_backoff_restarts_for_a_new_head(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        controller = BacklogController(bus, FailingUpload(), backlog)
        backlog.add(_record_segment(tmp_path, "2026-08-12_10-00-00"))
        backlog.add(_record_segment(tmp_path, "2026-08-12_12-00-00"))
        controller.run_once()
        controller.run_once()
        assert controller.wait_seconds == 10

        # The drop clears the stuck head, so the segment behind it starts fresh
        # rather than inheriting a wait it never earned.
        with patch.object(backlog, "is_below_floor", side_effect=[True, False]):
            controller.run_once()

        assert controller.wait_seconds == 5

    def test_a_success_resets_the_wait(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        controller = BacklogController(bus, FlakyUpload(failures=2), backlog)
        backlog.add(_record_segment(tmp_path, "2026-08-12_10-00-00"))
        controller.run_once()
        controller.run_once()
        grown = controller.wait_seconds

        controller.run_once()

        assert controller.wait_seconds < grown


class TestReclaimingSpace:
    def test_the_drop_runs_on_a_failing_pass(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        controller = BacklogController(bus, FailingUpload(), backlog)
        oldest = backlog.add(_record_segment(tmp_path, "2026-08-12_10-00-00"))
        newest = backlog.add(_record_segment(tmp_path, "2026-08-12_12-00-00"))

        with patch.object(backlog, "is_below_floor", side_effect=[True, False]):
            controller.run_once()

        assert not oldest.exists()
        assert newest.is_file()
        assert backlog.dropped_total == 1

    def test_the_drop_stops_when_the_backlog_is_empty(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        controller = BacklogController(bus, FailingUpload(), backlog)
        backlog.add(_record_segment(tmp_path, "2026-08-12_10-00-00"))

        with patch.object(
            Backlog,
            "free_bytes",
            return_value=0,
        ):
            controller.run_once()

        assert backlog.size() == 0
        assert backlog.dropped_total == 1

    def test_nothing_is_dropped_with_room_to_spare(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        controller = BacklogController(bus, FailingUpload(), backlog)
        segment = backlog.add(_record_segment(tmp_path))

        with patch.object(Backlog, "free_bytes", return_value=10 * _GIB):
            controller.run_once()

        assert segment.is_file()
        assert backlog.dropped_total == 0


class TestWithoutAnUploadBackend:
    def test_a_pass_keeps_the_segment_and_publishes_nothing(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        received = _uploaded_events(bus)
        controller = BacklogController(bus, None, backlog)
        segment = backlog.add(_record_segment(tmp_path))

        controller.run_once()
        bus.process_pending()

        assert segment.is_file()
        assert received == []
        assert backlog.uploaded_total == 0
        assert controller.wait_seconds == 5

    def test_the_drop_still_runs(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        controller = BacklogController(bus, None, backlog)
        oldest = backlog.add(_record_segment(tmp_path, "2026-08-12_10-00-00"))
        newest = backlog.add(_record_segment(tmp_path, "2026-08-12_12-00-00"))

        with patch.object(backlog, "is_below_floor", side_effect=[True, False]):
            controller.run_once()

        assert not oldest.exists()
        assert newest.is_file()
        assert backlog.dropped_total == 1


class TestWorkerThread:
    def test_start_runs_passes_and_close_stops_the_thread(
        self, bus: EventBus, backlog: Backlog, tmp_path: Path
    ) -> None:
        upload = FakeUpload()
        controller = BacklogController(bus, upload, backlog)
        segment = backlog.add(_record_segment(tmp_path))
        controller._wait_seconds = 0.01

        controller.start()
        assert controller.is_running
        remaining_tries = 100
        while segment.exists() and remaining_tries > 0:
            remaining_tries -= 1
            sleep(0.02)
        controller.close()

        assert not segment.exists()
        assert not controller.is_running

    def test_close_without_start_does_not_raise(
        self, bus: EventBus, backlog: Backlog
    ) -> None:
        BacklogController(bus, FakeUpload(), backlog).close()
