"""The on-disk stores of recorded segments that still have a step ahead of them."""

import logging
import os
import re
from datetime import datetime as dt
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)

_PENDING_DIR_NAME = "pending"
_UPLOADED_DIR_NAME = "uploaded"
_TIMESTAMP_PATTERN = re.compile(r"_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")


class Backlog:
    """The files that have left one directory but not yet finished their work.

    A backlog is a plain directory. There is no index and no sidecar file: a
    file is in the backlog if it is in that directory. Files get there by being
    renamed out of the source directory, which only stays atomic while both
    directories are on one filesystem; the constructor checks that.

    Two threads use a backlog without a lock. The producer only adds, and
    always the newest file; the worker only removes, and always the oldest. The
    two therefore never touch the same file.
    """

    def __init__(self, source_dir: Path, target_dir: Path) -> None:
        """Create both directories if they do not exist yet.

        Args:
            source_dir (Path): Directory the files arrive in.
            target_dir (Path): Directory the backlog keeps the files in.

        Raises:
            ValueError: If the source and target directory are identical or are
                on different filesystems.
        """
        source_dir = source_dir.expanduser()
        source_dir.mkdir(parents=True, exist_ok=True)
        self._source = source_dir.resolve()

        target_dir = target_dir.expanduser()
        target_dir.mkdir(parents=True, exist_ok=True)
        self._target = target_dir.resolve()

        if self._source == self._target:
            raise ValueError(
                f"Source and backlog directory must differ, both are {self._source}"
            )
        if self._source.stat().st_dev != self._target.stat().st_dev:
            raise ValueError(
                f"Backlog directory {self._target} must be on the same "
                f"filesystem as {self._source} so that moving a file "
                f"stays atomic"
            )

    @property
    def source(self) -> Path:
        """Return the directory the files arrive in."""
        return self._source

    @property
    def directory(self) -> Path:
        """Return the directory holding the files that are waiting."""
        return self._target

    def add(self, file: Path) -> Path:
        """Accept a file into the backlog and return its new path.

        The file keeps its name, because the name carries the timestamp the
        backlog is ordered by.

        Args:
            file (Path): The file to take in.

        Returns:
            Path: Where the file now lives.
        """
        destination = self._target / file.name
        file.rename(destination)
        logger.debug("Accepted %s into the backlog", destination.name)
        return destination

    def oldest(self) -> Path | None:
        """Return the file to work on next, or None when the backlog is empty.

        Files are ordered by the timestamp in the filename rather than by file
        times, which a copy or a touch would change. A name without a timestamp
        sorts behind every name that has one, so a stray file is handled last
        and never blocks the files behind it.
        """
        names = self._file_names()
        if not names:
            return None
        return self._target / min(names, key=_sort_key)

    def remove(self, file: Path) -> None:
        """Delete a file from the backlog.

        Only the worker draining the backlog may call this. A file that is
        already gone is not an error: the point is that it is no longer in the
        backlog.

        Args:
            file (Path): The file to delete.
        """
        file.unlink(missing_ok=True)

    def size(self) -> int:
        """Return how many files are in the backlog."""
        return len(self._file_names())

    def free_bytes(self) -> int:
        """Return the free space on the filesystem holding the files."""
        return int(psutil.disk_usage(str(self._source)).free)

    def oldest_age_seconds(self) -> float | None:
        """Return how long the oldest file has waited, in seconds.

        Returns None when the backlog is empty, or when the oldest file carries
        no timestamp to measure from.
        """
        oldest = self.oldest()
        if oldest is None:
            return None
        timestamp = _timestamp_of(oldest.name)
        if timestamp is None:
            return None
        return (dt.now() - timestamp).total_seconds()

    def _file_names(self) -> list[str]:
        """Return the names of the files in the backlog, in no order.

        Only the directory listing is read, never the files themselves, so
        counting the backlog stays cheap as it grows.
        """
        with os.scandir(self._target) as entries:
            return [entry.name for entry in entries if entry.is_file()]


class UploadBacklog(Backlog):
    """The recorded segments that are not on the server yet.

    Segments arrive in the video directory the camera records into and wait in
    `<video_dir>/pending` until the upload worker has them on the server.
    """

    def __init__(self, video_dir: Path, video_format: str, min_free_bytes: int) -> None:
        """Create the backlog directory below `video_dir`.

        Args:
            video_dir (Path): Directory the camera records into.
            video_format (str): Suffix of a recorded video file, e.g. `h264`.
            min_free_bytes (int): Free space below which segments are dropped to
                keep recording.

        Raises:
            ValueError: If the backlog directory turns out to be `video_dir`
                itself, or to sit on a different filesystem.
        """
        super().__init__(
            source_dir=video_dir,
            target_dir=video_dir.expanduser() / _PENDING_DIR_NAME,
        )
        self._video_format = video_format
        self._min_free_bytes = min_free_bytes

        self._uploaded_total = 0
        self._dropped_total = 0

    @property
    def video_dir(self) -> Path:
        """Return the directory the camera records into."""
        return self._source

    @property
    def pending(self) -> Path:
        """Return the directory holding the segments waiting to be uploaded."""
        return self._target

    @property
    def uploaded_total(self) -> int:
        """Return how many segments have been uploaded since startup."""
        return self._uploaded_total

    @property
    def dropped_total(self) -> int:
        """Return how many segments have been dropped to reclaim space."""
        return self._dropped_total

    def is_below_floor(self) -> bool:
        """Return whether space has to be reclaimed to keep recording."""
        return self.free_bytes() <= self._min_free_bytes

    def recover_unfinished_segments(self) -> int:
        """Accept every video file left directly in the video directory.

        This runs at startup, before recording begins, so anything still lying
        in the video directory is from a recording that was cut short. Such a
        segment is incomplete but holds footage, and how much footage depends on
        the configured segment length, so it is uploaded rather than dropped.

        The backlog is untouched, because the listing does not recurse, and so
        are logs and the preview image, because only the video suffix is moved.

        Returns:
            int: How many files were moved into the backlog.
        """
        recovered = 0
        for path in list(self._source.iterdir()):
            if not path.is_file() or path.suffix != f".{self._video_format}":
                continue
            self.add(path)
            recovered += 1
        return recovered

    def count_uploaded(self) -> None:
        """Record that a segment reached the server."""
        self._uploaded_total += 1

    def count_dropped(self) -> None:
        """Record that a segment was deleted to reclaim space."""
        self._dropped_total += 1


class NotificationBacklog(Backlog):
    """The segments that are on the server but not announced yet.

    A segment that reached the server moves out of `<video_dir>/pending` into
    `<video_dir>/uploaded` and waits there until the notification about it has
    been sent. Keeping the file until then means a notification that fails can
    be sent again later, and a segment is only deleted once both steps are
    done.
    """

    def __init__(self, video_dir: Path) -> None:
        """Create the backlog directory below `video_dir`.

        Args:
            video_dir (Path): Directory the camera records into.

        Raises:
            ValueError: If the two directories turn out to be the same one, or
                to sit on different filesystems.
        """
        video_dir = video_dir.expanduser()
        super().__init__(
            source_dir=video_dir / _PENDING_DIR_NAME,
            target_dir=video_dir / _UPLOADED_DIR_NAME,
        )

        self._notified_total = 0

    @property
    def pending(self) -> Path:
        """Return the directory the uploaded segments come from."""
        return self._source

    @property
    def uploaded(self) -> Path:
        """Return the directory holding the segments waiting to be announced."""
        return self._target

    @property
    def notified_total(self) -> int:
        """Return how many segments have been announced since startup."""
        return self._notified_total

    def count_notified(self) -> None:
        """Record that a notification about a segment was sent."""
        self._notified_total += 1


def _timestamp_of(name: str) -> dt| None:
    """Return the timestamp encoded in a segment's filename, if it has one.

    The fields are read from their fixed places in the name. A date that cannot
    exist counts as no timestamp at all.

    Args:
        name (str): The filename to parse, without its directory.

    Returns:
        dt | None: The timestamp, or None when the name does not carry one.
    """
    match = _TIMESTAMP_PATTERN.search(name)
    if match is None:
        return None
    stamp = match.group(1)
    try:
        return dt(
            year=int(stamp[0:4]),
            month=int(stamp[5:7]),
            day=int(stamp[8:10]),
            hour=int(stamp[11:13]),
            minute=int(stamp[14:16]),
            second=int(stamp[17:19]),
        )
    except ValueError:
        return None


def _sort_key(name: str) -> tuple[int, dt | str]:
    """Return an oldest-first sort key that tolerates unparsable names.

    Args:
        name (str): The filename to build a key for.

    Returns:
        tuple[int, dt | str]: A key that sorts every timestamped name before
            every name without a timestamp.
    """
    timestamp = _timestamp_of(name)
    if timestamp is None:
        return (1, name)
    return (0, timestamp)
