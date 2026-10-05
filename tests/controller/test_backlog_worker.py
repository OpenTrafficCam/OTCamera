from collections.abc import Callable
from threading import Event
from time import sleep

import pytest

from OTCamera.controller import backlog_worker as backlog_worker_module
from OTCamera.controller.backlog_worker import BacklogWorker


def _worker(run_once: Callable[[], None] | None = None) -> BacklogWorker:
    return BacklogWorker("Upload", run_once or (lambda: None))


class TestBackingOff:
    def test_the_wait_starts_at_the_idle_interval(self) -> None:
        assert _worker().wait_seconds == 5

    def test_the_first_failure_waits_five_seconds_and_each_next_one_doubles(
        self,
    ) -> None:
        worker = _worker()
        worker.note_working_on("clip.h264")

        waits = []
        for _ in range(4):
            worker.note_failure(ConnectionError("away"))
            waits.append(worker.wait_seconds)

        assert waits == [5, 10, 20, 40]

    def test_the_wait_is_capped(self) -> None:
        worker = _worker()
        worker.note_working_on("clip.h264")

        for _ in range(20):
            worker.note_failure(ConnectionError("away"))

        assert worker.wait_seconds == 300

    def test_reaching_another_item_starts_it_off_with_a_fresh_count(self) -> None:
        worker = _worker()
        worker.note_working_on("first.h264")
        worker.note_failure(ConnectionError("away"))
        worker.note_failure(ConnectionError("away"))
        assert worker.wait_seconds == 10

        worker.note_working_on("second.h264")
        worker.note_failure(ConnectionError("away"))

        assert worker.wait_seconds == 5

    def test_staying_on_the_same_item_keeps_counting(self) -> None:
        worker = _worker()
        worker.note_working_on("clip.h264")
        worker.note_failure(ConnectionError("away"))

        worker.note_working_on("clip.h264")
        worker.note_failure(ConnectionError("away"))

        assert worker.wait_seconds == 10

    def test_an_item_that_goes_through_ends_the_backoff(self) -> None:
        worker = _worker()
        worker.note_working_on("clip.h264")
        worker.note_failure(ConnectionError("away"))
        worker.note_failure(ConnectionError("away"))

        worker.note_success()
        worker.note_working_on("clip.h264")
        worker.note_failure(ConnectionError("away"))

        assert worker.wait_seconds == 5

    def test_an_empty_backlog_ends_the_backoff(self) -> None:
        worker = _worker()
        worker.note_working_on("clip.h264")
        worker.note_failure(ConnectionError("away"))
        worker.note_failure(ConnectionError("away"))

        worker.note_empty()

        assert worker.wait_seconds == 5


class TestThread:
    def test_is_not_running_before_it_is_started(self) -> None:
        assert not _worker().is_running

    def test_runs_passes_until_it_is_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(backlog_worker_module, "_IDLE_WAIT_SECONDS", 0.01)
        passes = []
        worker = _worker(lambda: passes.append(1))

        worker.start()
        assert worker.is_running
        remaining_tries = 100
        while not passes and remaining_tries > 0:
            remaining_tries -= 1
            sleep(0.02)
        assert worker.close()

        assert passes
        assert not worker.is_running

    def test_a_pass_that_raises_does_not_stop_the_worker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(backlog_worker_module, "_IDLE_WAIT_SECONDS", 0.01)
        attempts = []

        def run_once() -> None:
            attempts.append(1)
            raise RuntimeError("something unexpected")

        worker = _worker(run_once)

        worker.start()
        remaining_tries = 100
        while len(attempts) < 2 and remaining_tries > 0:
            remaining_tries -= 1
            sleep(0.02)
        worker.close()

        assert len(attempts) >= 2

    def test_starting_twice_keeps_the_one_thread(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(backlog_worker_module, "_IDLE_WAIT_SECONDS", 0.01)
        worker = _worker()

        worker.start()
        thread = worker._thread
        worker.start()

        assert worker._thread is thread
        worker.close()


class TestClose:
    def test_reports_success_when_it_was_never_started(self) -> None:
        assert _worker().close()

    def test_reports_success_once_the_thread_is_gone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(backlog_worker_module, "_IDLE_WAIT_SECONDS", 0.01)
        worker = _worker()
        worker.start()

        assert worker.close()

    def test_reports_failure_when_a_pass_will_not_end(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(backlog_worker_module, "_IDLE_WAIT_SECONDS", 0.01)
        monkeypatch.setattr(backlog_worker_module, "CLOSE_TIMEOUT_SECONDS", 0.05)
        entered = Event()
        release = Event()

        def run_once() -> None:
            entered.set()
            release.wait()

        worker = _worker(run_once)

        worker.start()
        assert entered.wait(timeout=2), "the worker never started its pass"
        stopped = worker.close()
        release.set()

        assert not stopped

    def test_a_pass_can_see_that_the_worker_is_closing(self) -> None:
        worker = _worker()
        assert not worker.is_closing

        worker.close()

        assert worker.is_closing
