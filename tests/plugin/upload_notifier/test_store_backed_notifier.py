from pathlib import Path
from time import sleep

import pytest

from OTCamera.controller.message_store import MessageStore
from OTCamera.domain.notifier import Notifier
from OTCamera.plugin.upload_notifier.store_backed_notifier import StoreBackedNotifier


class FakeNotifier(Notifier[str]):
    def __init__(self) -> None:
        self.delivered: list[str] = []
        self.closed = False

    def notify(self, payload: str) -> None:
        self.delivered.append(payload)

    def close(self) -> None:
        self.closed = True


class FailingNotifier(Notifier[str]):
    def __init__(self) -> None:
        self.attempted: list[str] = []

    def notify(self, payload: str) -> None:
        self.attempted.append(payload)
        raise RuntimeError("delivery failed")

    def close(self) -> None:
        pass


class FlakyNotifier(Notifier[str]):
    def __init__(self, failures: int) -> None:
        self._remaining_failures = failures

    def notify(self, payload: str) -> None:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("delivery failed")

    def close(self) -> None:
        pass


@pytest.fixture
def store(tmp_path: Path) -> MessageStore:
    return MessageStore(message_dir=tmp_path)


def _stored_message(message_dir: Path, name: str, content: str) -> Path:
    message = message_dir / name
    message.write_text(content)
    return message


class TestNotify:
    def test_files_the_message_without_delivering(self, store: MessageStore) -> None:
        delivery = FakeNotifier()
        notifier = StoreBackedNotifier(delivery, store)

        notifier.notify("hello")

        assert store.size() == 1
        assert delivery.delivered == []

    def test_does_not_start_a_thread_on_construction(self, store: MessageStore) -> None:
        notifier = StoreBackedNotifier(FakeNotifier(), store)

        assert not notifier.is_running


class TestSuccessfulPass:
    def test_delivers_everything_and_empties_the_store(
        self, store: MessageStore, tmp_path: Path
    ) -> None:
        delivery = FakeNotifier()
        notifier = StoreBackedNotifier(delivery, store)
        _stored_message(tmp_path, "002", "second")
        _stored_message(tmp_path, "001", "first")

        notifier.run_once()

        assert delivery.delivered == ["first", "second"]
        assert store.size() == 0
        assert notifier.wait_seconds == 5

    def test_an_empty_store_delivers_nothing(self, store: MessageStore) -> None:
        delivery = FakeNotifier()
        notifier = StoreBackedNotifier(delivery, store)

        notifier.run_once()

        assert delivery.delivered == []


class TestFailingPass:
    def test_keeps_the_message_and_the_ones_behind_it(
        self, store: MessageStore, tmp_path: Path
    ) -> None:
        delivery = FailingNotifier()
        notifier = StoreBackedNotifier(delivery, store)
        _stored_message(tmp_path, "001", "first")
        _stored_message(tmp_path, "002", "second")

        notifier.run_once()

        assert delivery.attempted == ["first"]
        assert store.size() == 2

    def test_backs_off_from_five_seconds_by_doubling(
        self, store: MessageStore, tmp_path: Path
    ) -> None:
        notifier = StoreBackedNotifier(FailingNotifier(), store)
        _stored_message(tmp_path, "001", "first")

        waits = []
        for _ in range(4):
            notifier.run_once()
            waits.append(notifier.wait_seconds)

        assert waits == [5, 10, 20, 40]

    def test_caps_the_wait(self, store: MessageStore, tmp_path: Path) -> None:
        notifier = StoreBackedNotifier(FailingNotifier(), store)
        _stored_message(tmp_path, "001", "first")

        for _ in range(20):
            notifier.run_once()

        assert notifier.wait_seconds == 300

    def test_retries_the_same_message(
        self, store: MessageStore, tmp_path: Path
    ) -> None:
        delivery = FailingNotifier()
        notifier = StoreBackedNotifier(delivery, store)
        _stored_message(tmp_path, "001", "first")
        _stored_message(tmp_path, "002", "second")

        notifier.run_once()
        notifier.run_once()

        assert delivery.attempted == ["first", "first"]

    def test_the_backoff_restarts_for_a_new_head(
        self, store: MessageStore, tmp_path: Path
    ) -> None:
        notifier = StoreBackedNotifier(FailingNotifier(), store)
        stuck = _stored_message(tmp_path, "001", "first")
        _stored_message(tmp_path, "002", "second")
        notifier.run_once()
        notifier.run_once()
        assert notifier.wait_seconds == 10

        stuck.unlink()
        notifier.run_once()

        assert notifier.wait_seconds == 5

    def test_a_success_resets_the_wait(
        self, store: MessageStore, tmp_path: Path
    ) -> None:
        notifier = StoreBackedNotifier(FlakyNotifier(failures=2), store)
        _stored_message(tmp_path, "001", "first")
        notifier.run_once()
        notifier.run_once()
        grown = notifier.wait_seconds

        notifier.run_once()

        assert notifier.wait_seconds < grown


class TestUnreadableMessage:
    def test_is_set_aside_and_the_pass_continues(
        self, store: MessageStore, tmp_path: Path
    ) -> None:
        delivery = FakeNotifier()
        notifier = StoreBackedNotifier(delivery, store)
        (tmp_path / "001").write_bytes(b"\xff")
        _stored_message(tmp_path, "002", "second")

        notifier.run_once()

        assert delivery.delivered == ["second"]
        assert store.size() == 0
        assert (tmp_path / "unreadable" / "001").exists()


class TestWorkerThread:
    def test_a_notification_is_delivered_without_waiting_a_full_interval(
        self, store: MessageStore
    ) -> None:
        delivery = FakeNotifier()
        notifier = StoreBackedNotifier(delivery, store)

        notifier.start()
        assert notifier.is_running
        notifier.notify("hello")
        remaining_tries = 100
        while store.size() > 0 and remaining_tries > 0:
            remaining_tries -= 1
            sleep(0.02)
        notifier.close()

        assert delivery.delivered == ["hello"]
        assert not notifier.is_running

    def test_a_new_message_does_not_shorten_the_wait_after_a_failure(
        self, store: MessageStore, tmp_path: Path
    ) -> None:
        delivery = FailingNotifier()
        notifier = StoreBackedNotifier(delivery, store)
        _stored_message(tmp_path, "001", "first")
        notifier.run_once()

        notifier.start()
        notifier.notify("second")
        sleep(0.2)
        notifier.close()

        assert delivery.attempted == ["first"]

    def test_close_stops_the_thread_and_closes_the_wrapped_notifier(
        self, store: MessageStore
    ) -> None:
        delivery = FakeNotifier()
        notifier = StoreBackedNotifier(delivery, store)
        notifier.start()

        notifier.close()

        assert not notifier.is_running
        assert delivery.closed

    def test_close_without_start_does_not_raise(self, store: MessageStore) -> None:
        StoreBackedNotifier(FakeNotifier(), store).close()

    def test_a_pass_stops_delivering_once_close_is_called(
        self, store: MessageStore, tmp_path: Path
    ) -> None:
        delivery = FakeNotifier()
        notifier = StoreBackedNotifier(delivery, store)
        _stored_message(tmp_path, "001", "first")
        _stored_message(tmp_path, "002", "second")

        notifier.close()
        notifier.run_once()

        assert delivery.delivered == []
        assert store.size() == 2
