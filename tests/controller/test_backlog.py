from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from OTCamera.controller.backlog import Backlog

_GIB = 1024 * 1024 * 1024


def _backlog(video_dir: Path, min_free_bytes: int = 0) -> Backlog:
    return Backlog(
        video_dir=video_dir,
        video_format="h264",
        min_free_bytes=min_free_bytes,
    )


def _segment(video_dir: Path, timestamp: str, content: bytes = b"x") -> Path:
    segment = video_dir / f"cam_FR20_{timestamp}.h264"
    segment.write_bytes(content)
    return segment


class TestConstructor:
    def test_creates_the_pending_directory(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path / "videos")

        assert backlog.pending.is_dir()

    def test_accepts_an_existing_pending_directory(self, tmp_path: Path) -> None:
        (tmp_path / "pending").mkdir()

        assert _backlog(tmp_path).pending == (tmp_path / "pending").resolve()

    def test_rejects_a_pending_dir_that_is_the_video_dir_itself(
        self, tmp_path: Path
    ) -> None:
        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        (video_dir / "pending").symlink_to(video_dir, target_is_directory=True)

        with pytest.raises(ValueError):
            _backlog(video_dir)

    def test_rejects_a_pending_dir_on_another_filesystem(self, tmp_path: Path) -> None:
        devices = iter([SimpleNamespace(st_dev=1), SimpleNamespace(st_dev=2)])

        with patch(
            "OTCamera.controller.backlog.Path.stat",
            side_effect=lambda *args, **kwargs: next(devices),
        ):
            with pytest.raises(ValueError):
                _backlog(tmp_path)


class TestAdd:
    def test_moves_the_segment_into_pending(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        segment = _segment(tmp_path, "2026-08-12_10-00-00")

        moved = backlog.add(segment)

        assert moved == backlog.pending / segment.name
        assert moved.is_file()
        assert not segment.exists()

    def test_leaves_nothing_behind_in_the_video_dir(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        backlog.add(_segment(tmp_path, "2026-08-12_10-00-00"))

        assert [path.name for path in tmp_path.iterdir()] == ["pending"]

    def test_keeps_the_segment_name_unchanged(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        segment = _segment(tmp_path, "2026-08-12_10-00-00")

        assert backlog.add(segment).name == segment.name


class TestOldest:
    def test_is_none_on_an_empty_backlog(self, tmp_path: Path) -> None:
        assert _backlog(tmp_path).oldest() is None

    def test_orders_by_the_filename_timestamp_not_mtime(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        # Written newest-name-first, so an mtime-based implementation fails.
        newest = backlog.add(_segment(tmp_path, "2026-08-12_12-00-00"))
        oldest = backlog.add(_segment(tmp_path, "2026-08-12_10-00-00"))

        assert backlog.oldest() == oldest
        assert backlog.oldest() != newest

    def test_a_name_without_a_timestamp_sorts_last(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        stray = tmp_path / "stray.h264"
        stray.write_bytes(b"x")
        backlog.add(stray)
        timestamped = backlog.add(_segment(tmp_path, "2026-08-12_10-00-00"))

        assert backlog.oldest() == timestamped

    def test_returns_a_stray_file_once_it_is_the_only_one(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        stray = tmp_path / "stray.h264"
        stray.write_bytes(b"x")
        moved = backlog.add(stray)

        assert backlog.oldest() == moved

    def test_ignores_subdirectories_of_pending(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        (backlog.pending / "subdir").mkdir()

        assert backlog.oldest() is None


class TestRemove:
    def test_deletes_the_segment(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        segment = backlog.add(_segment(tmp_path, "2026-08-12_10-00-00"))

        backlog.remove(segment)

        assert not segment.exists()

    def test_does_not_raise_when_the_file_is_already_gone(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)

        backlog.remove(backlog.pending / "missing.h264")


class TestSize:
    def test_counts_the_segments_in_pending(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        backlog.add(_segment(tmp_path, "2026-08-12_10-00-00"))
        backlog.add(_segment(tmp_path, "2026-08-12_11-00-00"))

        assert backlog.size() == 2

    def test_is_zero_on_an_empty_backlog(self, tmp_path: Path) -> None:
        assert _backlog(tmp_path).size() == 0


class TestFreeSpace:
    def test_is_below_floor_when_free_space_is_at_the_floor(
        self, tmp_path: Path
    ) -> None:
        backlog = _backlog(tmp_path, min_free_bytes=_GIB)

        with patch(
            "OTCamera.controller.backlog.psutil.disk_usage",
            return_value=SimpleNamespace(free=_GIB),
        ):
            assert backlog.is_below_floor()

    def test_is_not_below_floor_with_room_to_spare(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path, min_free_bytes=_GIB)

        with patch(
            "OTCamera.controller.backlog.psutil.disk_usage",
            return_value=SimpleNamespace(free=_GIB + 1),
        ):
            assert not backlog.is_below_floor()

    def test_free_bytes_reports_the_filesystem(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)

        with patch(
            "OTCamera.controller.backlog.psutil.disk_usage",
            return_value=SimpleNamespace(free=42),
        ):
            assert backlog.free_bytes() == 42


class TestOldestAgeSeconds:
    def test_is_none_on_an_empty_backlog(self, tmp_path: Path) -> None:
        assert _backlog(tmp_path).oldest_age_seconds() is None

    def test_is_none_when_the_oldest_name_carries_no_timestamp(
        self, tmp_path: Path
    ) -> None:
        backlog = _backlog(tmp_path)
        stray = tmp_path / "stray.h264"
        stray.write_bytes(b"x")
        backlog.add(stray)

        assert backlog.oldest_age_seconds() is None

    def test_grows_with_the_age_of_the_oldest_segment(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        backlog.add(_segment(tmp_path, "2020-01-01_00-00-00"))
        backlog.add(_segment(tmp_path, "2026-08-12_10-00-00"))

        age = backlog.oldest_age_seconds()

        assert age is not None
        assert age > 5 * 365 * 24 * 3600


class TestRecoverUnfinishedSegments:
    def test_moves_video_files_from_the_video_dir_into_the_backlog(
        self, tmp_path: Path
    ) -> None:
        backlog = _backlog(tmp_path)
        first = _segment(tmp_path, "2026-08-12_10-00-00")
        second = _segment(tmp_path, "2026-08-12_10-15-00")

        assert backlog.recover_unfinished_segments() == 2
        assert not first.exists()
        assert not second.exists()
        assert (backlog.pending / first.name).is_file()
        assert (backlog.pending / second.name).is_file()

    def test_keeps_the_content_of_a_recovered_segment(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        cut_short = _segment(tmp_path, "2026-08-12_10-00-00", content=b"half a video")

        backlog.recover_unfinished_segments()

        assert (backlog.pending / cut_short.name).read_bytes() == b"half a video"

    def test_leaves_the_backlog_logs_and_preview_alone(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)
        pending_segment = backlog.add(_segment(tmp_path, "2026-08-12_09-00-00"))
        log_file = tmp_path / "otcamera_2026-08-12_10-00-00.log"
        log_file.write_text("log")
        preview = tmp_path / "preview.jpg"
        preview.write_bytes(b"jpg")
        _segment(tmp_path, "2026-08-12_10-15-00")

        assert backlog.recover_unfinished_segments() == 1
        assert pending_segment.is_file()
        assert log_file.is_file()
        assert preview.is_file()
        assert backlog.size() == 2

    def test_is_zero_when_the_video_dir_holds_no_segments(self, tmp_path: Path) -> None:
        assert _backlog(tmp_path).recover_unfinished_segments() == 0


class TestCounters:
    def test_start_at_zero(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)

        assert backlog.uploaded_total == 0
        assert backlog.dropped_total == 0

    def test_count_uploads_and_drops(self, tmp_path: Path) -> None:
        backlog = _backlog(tmp_path)

        backlog.count_uploaded()
        backlog.count_dropped()
        backlog.count_dropped()

        assert backlog.uploaded_total == 1
        assert backlog.dropped_total == 2
