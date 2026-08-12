"""The on-disk store of recorded segments that are waiting to be uploaded."""

import logging
import re
from datetime import datetime as dt
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)

_PENDING_DIR_NAME = "pending"
_TIMESTAMP_PATTERN = re.compile(r"_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")
_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"


class Backlog:
    """The recorded segments that are not on the server yet.

    The backlog is a plain directory, `<video_dir>/pending`. There is no index
    and no sidecar file: a segment is in the backlog if it is in that
    directory. Segments get there by being renamed, which only stays atomic
    while both directories are on one filesystem; the constructor checks that.

    Two threads use the backlog without a lock. The camera thread only adds,
    and always the newest segment; the upload worker only removes, and always
    the oldest. The two therefore never touch the same file.
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
        self._video_dir = video_dir.expanduser().resolve()
        self._video_format = video_format
        self._min_free_bytes = min_free_bytes

        pending = self._video_dir / _PENDING_DIR_NAME
        pending.mkdir(parents=True, exist_ok=True)
        self._pending = pending.resolve()

        if self._pending == self._video_dir:
            raise ValueError(
                f"Backlog directory must differ from the video directory, "
                f"both are {self._video_dir}"
            )
        if self._video_dir.stat().st_dev != self._pending.stat().st_dev:
            raise ValueError(
                f"Backlog directory {self._pending} must be on the same "
                f"filesystem as {self._video_dir} so that moving a segment "
                f"stays atomic"
            )

        self._uploaded_total = 0
        self._dropped_total = 0

    @property
    def pending(self) -> Path:
        """Return the directory holding the segments waiting to be uploaded."""
        return self._pending

    @property
    def uploaded_total(self) -> int:
        """Return how many segments have been uploaded since startup."""
        return self._uploaded_total

    @property
    def dropped_total(self) -> int:
        """Return how many segments have been dropped to reclaim space."""
        return self._dropped_total

    def add(self, segment: Path) -> Path:
        """Accept a finished segment into the backlog and return its new path.

        The segment keeps its name, because the name carries the timestamp the
        backlog is ordered by. `recover_unfinished_segments` calls this at
        startup; once recording has started only the camera thread may.

        Args:
            segment (Path): The finished video file in the video directory.

        Returns:
            Path: Where the segment now lives.
        """
        destination = self._pending / segment.name
        segment.rename(destination)
        logger.debug("Accepted %s into the backlog", destination.name)
        return destination

    def oldest(self) -> Path | None:
        """Return the segment to upload next, or None when the backlog is empty.

        Segments are ordered by the timestamp in the filename rather than by
        file times, which a copy or a touch would change. A name without a
        timestamp sorts behind every name that has one, so a stray file is
        uploaded last and never blocks the segments behind it.
        """
        segments = self._segments()
        if not segments:
            return None
        return min(segments, key=_sort_key)

    def remove(self, segment: Path) -> None:
        """Delete a segment from the backlog.

        Only the upload worker may call this. A segment that is already gone is
        not an error: the point is that it is no longer in the backlog.

        Args:
            segment (Path): The segment to delete.
        """
        segment.unlink(missing_ok=True)

    def size(self) -> int:
        """Return how many segments are waiting to be uploaded."""
        return len(self._segments())

    def free_bytes(self) -> int:
        """Return the free space on the filesystem holding the segments."""
        return int(psutil.disk_usage(str(self._video_dir)).free)

    def is_below_floor(self) -> bool:
        """Return whether space has to be reclaimed to keep recording."""
        return self.free_bytes() <= self._min_free_bytes

    def oldest_age_seconds(self) -> float | None:
        """Return how long the oldest segment has waited, in seconds.

        Returns None when the backlog is empty, or when the oldest segment
        carries no timestamp to measure from.
        """
        oldest = self.oldest()
        if oldest is None:
            return None
        timestamp = _timestamp_of(oldest)
        if timestamp is None:
            return None
        return (dt.now() - timestamp).total_seconds()

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
        for path in list(self._video_dir.iterdir()):
            if not path.is_file() or path.suffix != f".{self._video_format}":
                continue
            self.add(path)
            recovered += 1
        return recovered

    def _segments(self) -> list[Path]:
        """Return the files currently in the backlog, in no particular order."""
        return [path for path in self._pending.iterdir() if path.is_file()]

    def count_uploaded(self) -> None:
        """Record that a segment reached the server."""
        self._uploaded_total += 1

    def count_dropped(self) -> None:
        """Record that a segment was deleted to reclaim space."""
        self._dropped_total += 1


def _timestamp_of(segment: Path) -> dt | None:
    """Return the timestamp encoded in a segment's filename, if it has one.

    Args:
        segment (Path): The segment whose name should be parsed.

    Returns:
        dt | None: The timestamp, or None when the name does not carry one.
    """
    match = _TIMESTAMP_PATTERN.search(segment.stem)
    if match is None:
        return None
    try:
        return dt.strptime(match.group(1), _TIMESTAMP_FORMAT)
    except ValueError:
        return None


def _sort_key(segment: Path) -> tuple[int, dt | str]:
    """Return an oldest-first sort key that tolerates unparseable names.

    Args:
        segment (Path): The segment to build a key for.

    Returns:
        tuple[int, dt | str]: A key that sorts every timestamped name before
            every name without a timestamp.
    """
    timestamp = _timestamp_of(segment)
    if timestamp is None:
        return (1, segment.name)
    return (0, timestamp)
