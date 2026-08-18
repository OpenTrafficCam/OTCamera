"""The on-disk store of messages that are waiting to be delivered."""

import os
from datetime import datetime
from pathlib import Path


class MessageStore:
    """The messages that are recorded but not yet delivered.

    The store is a plain directory with one file per message and no index:
    the filename carries the time the message was recorded, and the store
    hands the messages out in that order. A message only becomes visible
    once it is complete, so a reader never sees half of one.

    Two threads share the store without a lock. The thread that records
    messages only calls `add`, which always writes a new file; the thread
    that delivers them is the only caller of `remove` and `quarantine`,
    which always target the oldest message. The two therefore never touch
    the same file.
    """

    def __init__(self, message_dir: Path):
        """Create the store below `message_dir`.

        Args:
            message_dir (Path): Directory the messages are kept in.
        """
        self._message_dir = message_dir.expanduser().resolve()
        self._message_dir.mkdir(parents=True, exist_ok=True)
        # messages are written here first, see `add`.
        self._incomplete_dir = self._message_dir / "incomplete"
        self._incomplete_dir.mkdir(exist_ok=True)
        # messages nobody could read end up here, see `quarantine`.
        self._unreadable_dir = self._message_dir / "unreadable"

    def add(self, message: str) -> None:
        """Take a message into the store, to be delivered later.

        Args:
            message (str): The message to keep until it is delivered.
        """
        # use sub-second precision to support more than one
        # message per second.
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # _%f = microseconds

        # write the message next to the store and move it in once it is
        # complete, so a reader never picks up a half-written message and
        # delivers it empty. The move only stays safe against interruption
        # because both directories are on the same drive.
        tmp = self._incomplete_dir / ts

        with open(tmp, "w") as f:
            f.write(message)
            # get the content onto the drive before the move makes the
            # message visible, so it survives losing power.
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp, self._message_dir / ts)

    def _message_names(self) -> list[str]:
        """Return the names of the messages in the store, in no order."""
        with os.scandir(self._message_dir) as entries:
            return [entry.name for entry in entries if entry.is_file()]

    def oldest(self) -> Path | None:
        """Return the oldest message in the store."""
        names = sorted(self._message_names())

        if not names:
            return None

        return self._message_dir / names[0]

    def quarantine(self, ts: str) -> None:
        """Set a message with the given timestamp aside.

        The message is no longer handed out by the store but stays on the
        drive, so it can still be looked at once the camera is back.

        Args:
            ts (str): The name of the message to set aside.
        """
        self._unreadable_dir.mkdir(exist_ok=True)
        os.replace(self._message_dir / ts, self._unreadable_dir / ts)

    def remove(self, ts: str) -> None:
        """Remove a message with the given timestamp from the store.

        A message that is already gone is not an error: the point is that it
        is no longer in the store.

        Args:
            ts (str): The name of the message to remove.
        """
        fp = self._message_dir / ts
        fp.unlink(missing_ok=True)

    def size(self) -> int:
        """Return how many messages are waiting to be delivered."""
        return len(self._message_names())
