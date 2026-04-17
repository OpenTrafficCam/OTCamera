"""Camera recording orchestration."""

import base64
import errno
import logging
from datetime import datetime as dt
from pathlib import Path
from time import sleep
from typing import cast

import psutil
import requests
import urllib3

from OTCamera.config import Config
from OTCamera.domain.camera import (
    Camera,
    CameraClosedError,
    H264Level,
    H264Profile,
    VideoFormat,
)
from OTCamera.domain.events import (
    EventBus,
    PreviewCaptured,
    RecordingSplit,
    RecordingStarted,
    RecordingStopped,
)
from OTCamera.domain.led import LED

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

_BYTES_PER_GIB = 1024 * 1024 * 1024


class CameraController:
    """Orchestrate start/stop/split/capture operations for the camera."""

    def __init__(
        self,
        camera: Camera,
        config: Config,
        event_bus: EventBus,
        leds: dict[str, LED],
    ) -> None:
        self._camera = camera
        self._config = config
        self._event_bus = event_bus
        self._leds = leds
        self._current_video_file = self._video_filename()
        self._last_split_minute = -1
        self._current_interval = 0
        self._more_intervals = True

    @property
    def is_recording(self) -> bool:
        """Return whether the camera is currently recording."""
        return self._camera.is_recording

    @property
    def more_intervals(self) -> bool:
        """Return whether more intervals remain to be recorded."""
        return self._more_intervals

    @property
    def current_interval(self) -> int:
        """Return the current interval index."""
        return self._current_interval

    def start_recording(self) -> None:
        """Start recording if the camera is not already recording."""
        if self._camera.is_recording:
            return

        self.delete_old_files()
        self._set_annotation_text()
        self._current_video_file = self._video_filename()
        video = self._config.video
        self._camera.start_recording(
            save_file=self._current_video_file,
            video_format=cast(VideoFormat, video.format),
            resolution=video.resolution,
            bitrate=video.encoder.bitrate,
            h264_profile=cast(H264Profile, video.encoder.profile),
            h264_level=cast(H264Level, video.encoder.level),
            h264_quality=video.encoder.quality,
        )
        self._last_split_minute = dt.now().minute
        logger.info("Started recording: %s", self._current_video_file)
        self._led_recording_on()
        self._event_bus.publish(RecordingStarted(filename=self._current_video_file))
        self._wait_recording(2)
        self.capture()

    def stop_recording(self) -> None:
        """Stop recording if the camera is active."""
        if not self._camera.is_recording:
            return
        self._camera.stop_recording()
        self._led_recording_off()
        logger.info("Stopped recording. Videos: %d", self._current_interval)
        self._event_bus.publish(RecordingStopped())

    def split_if_interval_ends(self) -> None:
        """Split the recording when the configured interval boundary is reached."""
        current_minute = dt.now().minute
        interval = self._config.recording.interval_length
        if (current_minute % interval == 0) and (
            current_minute != self._last_split_minute
        ):
            self._last_split_minute = current_minute
            self._split()
            self._current_interval += 1
            num_intervals = self._config.recording.num_intervals
            if num_intervals > 0:
                self._more_intervals = self._current_interval < num_intervals
            if not self._more_intervals:
                logger.debug("Last interval reached")

        self._wait_recording(0.5)
        self._set_annotation_text()

    def capture(self) -> None:
        """Capture and optionally forward a preview image."""
        if not self._camera.is_recording:
            logger.warning("Cannot capture preview, camera not recording")
            return

        self._set_annotation_text()
        preview_path = self._preview_path()
        self._camera.capture(
            save_file=preview_path,
            image_format=self._config.preview.format,
            resolution=self._config.video.resolution,
        )
        logger.debug("Preview captured")
        self._try_send_preview(preview_path)
        self._event_bus.publish(PreviewCaptured(path=preview_path))

    def close(self) -> None:
        """Close the camera and swallow already-closed errors."""
        try:
            self._camera.close()
            logger.debug("Camera closed")
        except CameraClosedError:
            logger.debug("Camera already closed")

    def restart(self) -> None:
        """Reinitialize the camera backend."""
        logger.info("Restarting camera")
        self._camera.reinitialize()

    def delete_old_files(self) -> None:
        """Delete old recordings until enough free disk space is available."""
        video_dir = Path(self._config.video.dir).expanduser().resolve()
        min_free_bytes = self._config.recording.min_free_space * _BYTES_PER_GIB
        logger.debug("Checking disk space in %s", video_dir)

        current = Path(self._current_video_file) if self._camera.is_recording else None
        while psutil.disk_usage(str(video_dir)).free <= min_free_bytes:
            video_paths = [
                path
                for path in video_dir.iterdir()
                if path.suffix != ".log" and (current is None or path != current)
            ]
            if len(video_paths) <= 1:
                message = f"No space and no files to delete in {video_dir}"
                logger.error(message)
                raise OSError(errno.ENOSPC, message)
            oldest = min(video_paths, key=lambda path: path.stat().st_ctime)
            oldest.unlink()
            logger.info("Deleted %s", oldest)

    def _split(self) -> None:
        """Split recording to a new file and publish the completed segment."""
        previous_file = self._current_video_file
        new_file = self._video_filename()
        self._camera.split_recording(new_file)
        self._current_video_file = new_file
        logger.info("Split recording: %s", new_file)
        self._event_bus.publish(RecordingSplit(filename=previous_file))
        self.delete_old_files()

    def _wait_recording(self, timeout: int | float = 0) -> None:
        """Wait while recording or sleep when the camera is idle."""
        if self._camera.is_recording:
            self._camera.wait_recording(timeout)
            return
        sleep(timeout)

    def _video_filename(self) -> str:
        """Return the absolute path for the next video file."""
        config = self._config
        filename = (
            Path(config.video.dir)
            / f"{config.camera_name}_FR{config.camera.fps}_{self._current_dt()}."
            f"{config.video.format}"
        )
        return str(filename.expanduser().resolve())

    def _preview_path(self) -> str:
        """Return the absolute path for the preview image."""
        return str(Path(self._config.preview.path).expanduser().resolve())

    def _annotate_text(self) -> str:
        """Return the current annotation text."""
        return dt.now().strftime(f"{self._config.camera_name} %d.%m.%Y %H:%M:%S")

    @staticmethod
    def _current_dt() -> str:
        """Return the current timestamp for filenames."""
        return dt.now().strftime("%Y-%m-%d_%H-%M-%S")

    def _set_annotation_text(self) -> None:
        """Push the current annotation text into the camera backend."""
        self._camera.set_annotation_text(self._annotate_text())

    def _led_recording_on(self) -> None:
        """Enable the recording LED pattern."""
        led = self._leds.get("recording")
        if led is not None:
            led.blink(on_time=0.1, off_time=4.9, n=None, background=True)

    def _led_recording_off(self) -> None:
        """Disable the recording LED pattern."""
        led = self._leds.get("recording")
        if led is not None:
            led.pulse(fade_in_time=0.25, fade_out_time=0.25, n=4, background=True)

    def _try_send_preview(self, preview_path: str) -> None:
        """Forward the preview image to an external endpoint if enabled."""
        if not self._config.preview.send_to_external:
            return

        try:
            with open(preview_path, "rb") as file_handle:
                image = base64.b64encode(file_handle.read()).decode("utf-8")
            response = requests.post(
                self._config.preview.url,
                json={"frame": 0, "image": image},
                verify=False,
                timeout=10,
            )
        except Exception as exc:
            logger.warning("Error sending preview: %s", exc)
            return

        if response.status_code != 200:
            logger.warning("Preview send failed: %d", response.status_code)
            return
        logger.debug("Preview sent to external server")
