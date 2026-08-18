from pathlib import Path

from OTCamera.controller.message_store import MessageStore


def _store(message_dir: Path) -> MessageStore:
    return MessageStore(message_dir)


def _messages_on_drive(message_dir: Path) -> list[str]:
    return sorted(path.name for path in message_dir.iterdir() if path.is_file())


class TestConstructor:
    def test_creates_the_message_directory(self, tmp_path: Path) -> None:
        message_dir = tmp_path / "notices"

        _store(message_dir)

        assert message_dir.is_dir()

    def test_creates_missing_parent_directories(self, tmp_path: Path) -> None:
        message_dir = tmp_path / "state" / "notices"

        _store(message_dir)

        assert message_dir.is_dir()

    def test_accepts_a_directory_that_already_holds_messages(
        self, tmp_path: Path
    ) -> None:
        _store(tmp_path).add("kept")

        assert _store(tmp_path).size() == 1

    def test_leaves_the_unreadable_directory_uncreated(self, tmp_path: Path) -> None:
        _store(tmp_path)

        assert not (tmp_path / "unreadable").exists()


class TestAdd:
    def test_keeps_the_message_content(self, tmp_path: Path) -> None:
        store = _store(tmp_path)

        store.add("the message")

        oldest = store.oldest()
        assert oldest is not None
        assert oldest.read_text() == "the message"

    def test_leaves_nothing_behind_in_the_incomplete_directory(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)

        store.add("the message")

        assert list((tmp_path / "incomplete").iterdir()) == []

    def test_keeps_messages_recorded_in_the_same_second_apart(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)

        store.add("first")
        store.add("second")

        assert store.size() == 2
        assert len(_messages_on_drive(tmp_path)) == 2


class TestOldest:
    def test_is_none_on_an_empty_store(self, tmp_path: Path) -> None:
        assert _store(tmp_path).oldest() is None

    def test_hands_out_the_message_recorded_first(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("first")
        store.add("second")

        oldest = store.oldest()

        assert oldest is not None
        assert oldest.read_text() == "first"

    def test_advances_once_the_first_message_is_removed(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("first")
        store.add("second")
        first = store.oldest()
        assert first is not None

        store.remove(first.name)

        oldest = store.oldest()
        assert oldest is not None
        assert oldest.read_text() == "second"

    def test_ignores_the_stores_own_subdirectories(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("quarantined")
        quarantined = store.oldest()
        assert quarantined is not None
        store.quarantine(quarantined.name)

        assert store.oldest() is None


class TestQuarantine:
    def test_takes_the_message_out_of_the_store(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("unreadable")
        message = store.oldest()
        assert message is not None

        store.quarantine(message.name)

        assert store.size() == 0
        assert store.oldest() is None

    def test_keeps_the_message_on_the_drive(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("unreadable")
        message = store.oldest()
        assert message is not None

        store.quarantine(message.name)

        set_aside = tmp_path / "unreadable" / message.name
        assert set_aside.read_text() == "unreadable"

    def test_leaves_the_other_messages_alone(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("first")
        store.add("second")
        first = store.oldest()
        assert first is not None

        store.quarantine(first.name)

        remaining = store.oldest()
        assert remaining is not None
        assert remaining.read_text() == "second"
        assert store.size() == 1


class TestRemove:
    def test_deletes_the_message(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("delivered")
        message = store.oldest()
        assert message is not None

        store.remove(message.name)

        assert not message.exists()
        assert store.size() == 0

    def test_does_not_raise_when_the_message_is_already_gone(
        self, tmp_path: Path
    ) -> None:
        _store(tmp_path).remove("20260812_100000_000000")


class TestSize:
    def test_is_zero_on_an_empty_store(self, tmp_path: Path) -> None:
        assert _store(tmp_path).size() == 0

    def test_counts_the_messages_waiting(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("first")
        store.add("second")

        assert store.size() == 2

    def test_does_not_count_the_stores_own_subdirectories(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("quarantined")
        quarantined = store.oldest()
        assert quarantined is not None
        store.quarantine(quarantined.name)

        assert store.size() == 0
