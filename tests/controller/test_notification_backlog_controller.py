from pathlib import Path
from time import sleep
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from OTCamera.controller.backlog import NotificationBacklog, UploadBacklog
from OTCamera.controller.notification_backlog_controller import (
    NotificationBacklogController,
)
from OTCamera.domain.notifier import Notifier, UploadPayloadFactory
from OTCamera.domain.upload import Upload, UploadResult


class FakeUpload(Upload):
    def upload(self, file_path: Path) -> UploadResult:
        raise AssertionError("the notification worker must not upload anything")

    def is_available(self) -> bool:
        return True


class FakeNotifier(Notifier[str]):
    def __init__(self, failures: int = 0) -> None:
        self.delivered: list[str] = []
        self.attempted: list[str] = []
        self.is_closed = False
        self._remaining_failures = failures

    def notify(self, payload: str) -> None:
        self.attempted.append(payload)
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise ConnectionError("broker is away")
        self.delivered.append(payload)

    def close(self) -> None:
        self.is_closed = True


class FailingNotifier(FakeNotifier):
    def __init__(self) -> None:
        super().__init__(failures=0)

    def notify(self, payload: str) -> None:
        self.attempted.append(payload)
        raise ConnectionError("broker is away")


class NamePayloadFactory(UploadPayloadFactory[str]):
    """Builds a message that says which file it is about."""

    def create(self, upload: UploadResult) -> str:
        return f"notification for {upload.local_path.name}"


_GIB = 1024 * 1024 * 1024


@pytest.fixture
def backlog(tmp_path: Path) -> NotificationBacklog:
    UploadBacklog(video_dir=tmp_path, video_format="h264", min_free_bytes=0)
    return NotificationBacklog(video_dir=tmp_path, min_free_bytes=0)


@pytest.fixture
def backlog_with_a_floor(tmp_path: Path) -> NotificationBacklog:
    UploadBacklog(video_dir=tmp_path, video_format="h264", min_free_bytes=0)
    return NotificationBacklog(video_dir=tmp_path, min_free_bytes=_GIB)


def _controller(
    backlog: NotificationBacklog, notifier: Notifier[str]
) -> NotificationBacklogController:
    return NotificationBacklogController(
        backlog=backlog,
        upload=FakeUpload(),
        notifier=notifier,
        payload_factory=NamePayloadFactory(),
    )


def _uploaded_segment(
    backlog: NotificationBacklog,
    timestamp: str = "2026-08-12_10-00-00",
) -> Path:
    """Put a segment in the backlog the way a finished upload would."""
    segment = backlog.pending / f"cam_FR20_{timestamp}.h264"
    segment.write_bytes(b"video")
    return backlog.add(segment)


class TestConstruction:
    def test_does_not_start_a_thread(self, backlog: NotificationBacklog) -> None:
        assert not _controller(backlog, FakeNotifier()).is_running


class TestSuccessfulPass:
    def test_announces_the_segment_and_deletes_it(
        self, backlog: NotificationBacklog
    ) -> None:
        notifier = FakeNotifier()
        controller = _controller(backlog, notifier)
        segment = _uploaded_segment(backlog)

        controller.run_once()

        assert notifier.delivered == [f"notification for {segment.name}"]
        assert not segment.exists()
        assert backlog.size() == 0

    def test_counts_the_notification(self, backlog: NotificationBacklog) -> None:
        controller = _controller(backlog, FakeNotifier())
        _uploaded_segment(backlog)

        controller.run_once()

        assert backlog.notified_total == 1

    def test_drains_the_whole_backlog_oldest_first(
        self, backlog: NotificationBacklog
    ) -> None:
        notifier = FakeNotifier()
        controller = _controller(backlog, notifier)
        newest = _uploaded_segment(backlog, "2026-08-12_12-00-00")
        oldest = _uploaded_segment(backlog, "2026-08-12_10-00-00")

        controller.run_once()

        assert notifier.delivered == [
            f"notification for {oldest.name}",
            f"notification for {newest.name}",
        ]
        assert backlog.size() == 0

    def test_an_empty_backlog_announces_nothing(
        self, backlog: NotificationBacklog
    ) -> None:
        notifier = FakeNotifier()

        _controller(backlog, notifier).run_once()

        assert notifier.attempted == []


class TestFailingPass:
    def test_keeps_the_segment_when_the_broker_does_not_confirm(
        self, backlog: NotificationBacklog
    ) -> None:
        controller = _controller(backlog, FailingNotifier())
        segment = _uploaded_segment(backlog)

        controller.run_once()

        assert segment.is_file()
        assert backlog.size() == 1
        assert backlog.notified_total == 0

    def test_holds_back_the_segments_behind_the_failed_one(
        self, backlog: NotificationBacklog
    ) -> None:
        notifier = FailingNotifier()
        controller = _controller(backlog, notifier)
        oldest = _uploaded_segment(backlog, "2026-08-12_10-00-00")
        _uploaded_segment(backlog, "2026-08-12_12-00-00")

        controller.run_once()

        assert notifier.attempted == [f"notification for {oldest.name}"]
        assert backlog.size() == 2

    def test_retries_the_same_segment_on_the_next_pass(
        self, backlog: NotificationBacklog
    ) -> None:
        notifier = FailingNotifier()
        controller = _controller(backlog, notifier)
        oldest = _uploaded_segment(backlog, "2026-08-12_10-00-00")

        controller.run_once()
        controller.run_once()

        assert notifier.attempted == [f"notification for {oldest.name}"] * 2

    def test_a_failure_makes_the_worker_back_off(
        self, backlog: NotificationBacklog
    ) -> None:
        # how the wait grows is the worker's own business, see
        # tests/controller/test_backlog_worker.py.
        controller = _controller(backlog, FailingNotifier())
        _uploaded_segment(backlog)

        controller.run_once()
        after_one_failure = controller.wait_seconds
        controller.run_once()

        assert after_one_failure == 5
        assert controller.wait_seconds > after_one_failure

    def test_an_outage_that_ends_delivers_everything_that_waited(
        self, backlog: NotificationBacklog
    ) -> None:
        notifier = FakeNotifier(failures=2)
        controller = _controller(backlog, notifier)
        first = _uploaded_segment(backlog, "2026-08-12_10-00-00")
        second = _uploaded_segment(backlog, "2026-08-12_12-00-00")

        controller.run_once()
        controller.run_once()
        controller.run_once()

        assert notifier.delivered == [
            f"notification for {first.name}",
            f"notification for {second.name}",
        ]
        assert backlog.size() == 0
        assert controller.wait_seconds == 5

    def test_a_message_that_cannot_be_built_keeps_the_segment(
        self, backlog: NotificationBacklog
    ) -> None:
        notifier = FakeNotifier()
        controller = _controller(backlog, notifier)
        segment = _uploaded_segment(backlog)

        with patch.object(
            NamePayloadFactory, "create", side_effect=ValueError("no key prefix")
        ):
            controller.run_once()

        assert segment.is_file()
        assert notifier.attempted == []


class TestReclaimingSpace:
    def test_gives_up_the_oldest_notification_when_space_runs_short(
        self, backlog_with_a_floor: NotificationBacklog
    ) -> None:
        notifier = FailingNotifier()
        controller = _controller(backlog_with_a_floor, notifier)
        oldest = _uploaded_segment(backlog_with_a_floor, "2026-08-12_10-00-00")
        newest = _uploaded_segment(backlog_with_a_floor, "2026-08-12_12-00-00")

        with patch.object(
            NotificationBacklog, "is_below_floor", side_effect=[True, False]
        ):
            controller.run_once()

        assert not oldest.exists()
        assert newest.is_file()
        assert backlog_with_a_floor.dropped_total == 1

    def test_the_drop_runs_on_a_pass_that_cannot_reach_the_broker(
        self, backlog_with_a_floor: NotificationBacklog
    ) -> None:
        controller = _controller(backlog_with_a_floor, FailingNotifier())
        _uploaded_segment(backlog_with_a_floor, "2026-08-12_10-00-00")
        _uploaded_segment(backlog_with_a_floor, "2026-08-12_12-00-00")

        with patch(
            "OTCamera.controller.backlog.psutil.disk_usage",
            return_value=SimpleNamespace(free=0),
        ):
            controller.run_once()

        assert backlog_with_a_floor.size() == 0, (
            "the card has to be kept usable even when nothing can be announced"
        )
        assert backlog_with_a_floor.dropped_total == 2

    def test_a_segment_the_broker_refuses_for_good_is_cleared_eventually(
        self, backlog_with_a_floor: NotificationBacklog
    ) -> None:
        """Dropping the head is what lets the segments behind it through."""
        notifier = FakeNotifier(failures=1)
        controller = _controller(backlog_with_a_floor, notifier)
        poison = _uploaded_segment(backlog_with_a_floor, "2026-08-12_10-00-00")
        behind = _uploaded_segment(backlog_with_a_floor, "2026-08-12_12-00-00")

        controller.run_once()
        assert notifier.delivered == [], "the head blocks the one behind it"

        with patch.object(
            NotificationBacklog, "is_below_floor", side_effect=[True, False]
        ):
            controller.run_once()

        assert not poison.exists()
        assert notifier.delivered == [f"notification for {behind.name}"]

    def test_nothing_is_dropped_with_room_to_spare(
        self, backlog_with_a_floor: NotificationBacklog
    ) -> None:
        controller = _controller(backlog_with_a_floor, FailingNotifier())
        segment = _uploaded_segment(backlog_with_a_floor)

        with patch(
            "OTCamera.controller.backlog.psutil.disk_usage",
            return_value=SimpleNamespace(free=10 * _GIB),
        ):
            controller.run_once()

        assert segment.is_file()
        assert backlog_with_a_floor.dropped_total == 0

    def test_a_store_without_a_floor_keeps_everything(
        self, backlog: NotificationBacklog
    ) -> None:
        controller = _controller(backlog, FailingNotifier())
        segment = _uploaded_segment(backlog)

        with patch(
            "OTCamera.controller.backlog.psutil.disk_usage",
            return_value=SimpleNamespace(free=0),
        ):
            controller.run_once()

        assert segment.is_file()
        assert backlog.dropped_total == 0


class TestClose:
    def test_closes_the_notifier(self, backlog: NotificationBacklog) -> None:
        notifier = FakeNotifier()

        _controller(backlog, notifier).close()

        assert notifier.is_closed

    def test_close_without_start_does_not_raise(
        self, backlog: NotificationBacklog
    ) -> None:
        _controller(backlog, FakeNotifier()).close()


class TestWorkerThread:
    def test_start_runs_passes_and_close_stops_the_thread(
        self, backlog: NotificationBacklog
    ) -> None:
        notifier = FakeNotifier()
        controller = _controller(backlog, notifier)
        segment = _uploaded_segment(backlog)
        controller._worker._wait_seconds = 0.01

        controller.start()
        assert controller.is_running
        remaining_tries = 100
        while segment.exists() and remaining_tries > 0:
            remaining_tries -= 1
            sleep(0.02)
        controller.close()

        assert not segment.exists()
        assert not controller.is_running
        assert notifier.is_closed
