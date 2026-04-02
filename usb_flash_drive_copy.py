"""Copy recorded videos to a mounted USB flash drive."""

import csv
import logging
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, replace
from pathlib import Path

from OTCamera.bsl.board_provider import BoardComponents, BoardProvider
from OTCamera.config import Config
from OTCamera.domain.button import Button as DomainButton
from OTCamera.domain.led import LED
from OTCamera.log import setup_logging

logger = logging.getLogger(__name__)

COPY_INFO_CSV_SUFFIX = "_usb-copy-info.csv"


class IsNotADirectoryError(OSError):
    """Raised when a path is expected to be a directory but is not."""


class IllegalStateError(Exception):
    """Raised when the USB copy flow starts in an illegal hardware state."""


class UsbFlashDriveNotMountableError(Exception):
    """Raised when the USB flash drive could not be mounted."""


class UsbFlashDriveUnmountableError(Exception):
    """Raised when the USB flash drive could not be unmounted."""


@dataclass
class Video:
    """One video file and its copy/delete status."""

    filename: str
    path: Path
    copied: bool
    delete: bool

    @staticmethod
    def from_dict(data: dict[str, str], src: Path) -> "Video":
        """Build a Video entry from CSV data."""
        filename = data["filename"]
        copied = bool(re.search(r"yes|y|true|x|ja|j", data["copied"].lower()))
        delete = bool(re.search(r"yes|y|true|x|ja|j", data["delete"].lower()))
        return Video(
            filename=filename, path=src / filename, copied=copied, delete=delete
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the video entry for CSV output."""
        return {
            "filename": self.filename,
            "copied": self.copied,
            "delete": self.delete,
        }

    def __hash__(self) -> int:
        return hash(self.path)


class Led:
    """Thin wrapper around the domain LED interface for USB copy feedback."""

    def __init__(self, led: LED | None) -> None:
        self._led = led

    def blink(self, times: int | None = None, background: bool = True) -> None:
        """Blink the wrapped LED if present."""
        if self._led is not None:
            self._led.blink(n=times, background=background)
        time.sleep(2)

    def turn_off(self) -> None:
        """Turn the wrapped LED off if present."""
        if self._led is not None:
            self._led.off()

    def turn_on(self) -> None:
        """Turn the wrapped LED on if present."""
        if self._led is not None:
            self._led.on()
        time.sleep(2)


class PowerButton:
    """Monitor the power button and expose a shutdown flag."""

    def __init__(self, button: DomainButton) -> None:
        self._button = button
        self.shutdown_requested = False
        self._button.on_released(self._on_released)
        if not self._button.is_pressed:
            raise IllegalStateError("Power button must be active for the script to run")

    def _on_released(self) -> None:
        """Mark shutdown as requested when the power button is released."""
        logger.debug("Power button released")
        self.shutdown_requested = True


class CopyInformation:
    """Track which video files were copied and should be deleted."""

    def __init__(
        self,
        videos: set[Video],
        csv_file: Path,
        src_dir: Path,
        dest_dir: Path,
    ) -> None:
        self.videos = videos
        self.csv_file = csv_file
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self._validate_copy_info()

    @staticmethod
    def from_csv(file: Path, src_dir: Path, dest_dir: Path) -> "CopyInformation":
        """Load copy information from CSV."""
        videos: set[Video] = set()
        with open(file, mode="r", encoding="utf-8") as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                videos.add(Video.from_dict(row, src_dir))
        return CopyInformation(videos, file, src_dir, dest_dir)

    @staticmethod
    def get_copy_info_csv(directory: Path) -> Path:
        """Return the path of the copy-information CSV for this device."""
        return directory / f"{get_hostname()}{COPY_INFO_CSV_SUFFIX}"

    @staticmethod
    def create_new(src_dir: Path, dest_dir: Path, filetype: str) -> "CopyInformation":
        """Create fresh copy information from the current source directory."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        copy_csv_file = CopyInformation.get_copy_info_csv(dest_dir)
        copy_csv_file.touch()
        videos = {
            Video(path.name, path, copied=False, delete=False)
            for path in get_video_files(src_dir, filetype)
        }
        return CopyInformation(videos, copy_csv_file, src_dir, dest_dir)

    def remove(self, video: Video) -> None:
        """Remove a video from the tracked set."""
        self.videos.discard(video)

    def get_sorted_videos(self) -> list[Video]:
        """Return tracked videos sorted by filename."""
        return sorted(self.videos, key=lambda video: video.filename)

    def to_dict(self) -> list[dict[str, object]]:
        """Serialize tracked videos for CSV output."""
        return [video.to_dict() for video in self.get_sorted_videos()]

    def _validate_copy_info(self) -> None:
        """Reconcile tracked entries with the actual source and destination state."""
        videos_on_source = self._get_videos_from_source()

        for video in self.videos.copy():
            if not video.path.exists():
                logger.warning(
                    "File '%s' does not exist on OTCamera; removing from copy "
                    "information",
                    video.path,
                )
                self.remove(video)
                continue

            videos_on_source.discard(video)

            if (self.dest_dir / video.filename).exists():
                video.copied = True
                logger.debug("Video '%s' already copied", video.filename)

        self.videos.update(videos_on_source)

    def _get_videos_from_source(self) -> set[Video]:
        videos_on_source: set[Video] = set()
        for video_path in get_video_files(self.src_dir, "h264"):
            videos_on_source.add(
                Video(video_path.name, video_path, copied=False, delete=False)
            )
        return videos_on_source


@dataclass
class UsbFlashDrive:
    """Wrapper around a USB flash drive mount point."""

    mount_point: Path

    def mount(self) -> None:
        """Mount the USB flash drive."""
        if self.mount_point.is_mount():
            logger.warning("USB flash drive already mounted")
            return

        self.mount_point.mkdir(parents=True, exist_ok=True)
        return_code = subprocess.call(["sudo", "mount", str(self.mount_point)])
        if return_code != 0:
            raise UsbFlashDriveNotMountableError(
                f"Unable to mount USB flash drive to '{self.mount_point}'"
            )
        logger.info("USB flash drive mounted")

    def unmount(self) -> None:
        """Unmount the USB flash drive."""
        if not self.mount_point.is_mount():
            logger.warning("USB flash drive already unmounted")
            return

        return_code = subprocess.call(["sudo", "umount", str(self.mount_point)])
        if return_code != 0:
            raise UsbFlashDriveUnmountableError(
                f"Unable to unmount USB flash drive from '{self.mount_point}'"
            )
        logger.info("USB flash drive unmounted")


class OTCameraUsbCopier:
    """Copy recorded videos to USB and maintain copy metadata."""

    def __init__(
        self,
        power_led: Led,
        wifi_led: Led,
        rec_led: Led,
        src_dir: Path,
        usb_flash_drive: UsbFlashDrive,
        debug_mode_on: bool = False,
    ) -> None:
        self.power_led = power_led
        self.wifi_led = wifi_led
        self.rec_led = rec_led
        self.src_dir = src_dir
        self.usb_flash_drive = usb_flash_drive
        self.debug_mode_on = debug_mode_on

    def shutdown(self) -> None:
        """Shutdown OTCamera after the USB copy flow is complete."""
        self._turn_off_all_leds()
        self.power_led.blink(times=4, background=False)
        self.power_led.turn_on()
        if not self.debug_mode_on:
            logging.shutdown()
            subprocess.call(["sudo", "shutdown", "-h", "now"])

    def copy_to_usb(self, copy_info: CopyInformation) -> None:
        """Copy videos that are not yet marked as copied."""
        self.wifi_led.blink()
        logger.info("Start copying files")
        for video in copy_info.videos:
            if video.copied:
                logger.debug("Video '%s' already copied; skipping", video.path)
                continue
            if not video.path.exists():
                logger.warning("Video '%s' does not exist", video.path)
                continue
            try:
                shutil.copy2(src=video.path, dst=copy_info.dest_dir / video.filename)
            except IOError:
                logger.exception("Unable to copy video '%s'", video.path)
                continue
            video.copied = True
            logger.info("Video '%s' copied", video.path)
        logger.info("Copying videos to USB finished")
        self.wifi_led.turn_on()

    def delete(self, copy_info: CopyInformation) -> None:
        """Delete videos marked for deletion on OTCamera."""
        self.rec_led.blink()
        for video in copy_info.videos.copy():
            if not video.path.exists():
                logger.warning("Video '%s' does not exist", video.path)
                copy_info.remove(video)
                continue
            if not video.delete:
                logger.debug("Video '%s' not marked for deletion; skipping", video.path)
                continue

            if self.debug_mode_on:
                logger.debug("Debug mode on; mock deleting '%s'", video.path)
            else:
                try:
                    video.path.unlink()
                    copy_info.remove(video)
                except FileNotFoundError:
                    logger.exception(
                        "Video '%s' should exist but could not be found",
                        video.path,
                    )
                    continue
                except IOError:
                    logger.exception("Unable to delete video '%s'", video.path)
                    continue

            logger.info("Video '%s' deleted", video.path)
        self.rec_led.turn_on()

    def write_copy_info(self, copy_info: CopyInformation) -> None:
        """Persist copy information to CSV."""
        with open(copy_info.csv_file, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=["filename", "copied", "delete"],
            )
            writer.writeheader()
            for video_info in copy_info.to_dict():
                writer.writerow(video_info)

    def mount_usb_device(self) -> None:
        """Mount the USB flash drive."""
        self.usb_flash_drive.mount()

    def unmount_usb_device(self) -> None:
        """Unmount the USB flash drive and signal success via the power LED."""
        self.usb_flash_drive.unmount()
        self.power_led.turn_on()

    def _turn_off_all_leds(self) -> None:
        """Turn off all status LEDs."""
        self.power_led.turn_off()
        self.wifi_led.turn_off()
        self.rec_led.turn_off()


def get_video_files(directory: Path, filetype: str) -> list[Path]:
    """Return all video files of the requested type in the given directory."""
    if not directory.is_dir():
        raise IsNotADirectoryError(f"Path '{directory}' is not a directory")
    return [
        file
        for file in directory.iterdir()
        if file.is_file() and file.suffix == f".{filetype}"
    ]


def get_hostname() -> str:
    """Return the system hostname."""
    return socket.gethostname()


def build_usb_copier(
    config: Config,
    board: BoardComponents,
) -> tuple[OTCameraUsbCopier, PowerButton | None]:
    """Build the USB copier and optional power button wrapper."""
    src_dir = Path(config.video.dir)
    usb_flash_drive = UsbFlashDrive(Path(config.usb_mount_point))

    power_led = Led(board.leds.get("power"))
    rec_led = Led(board.leds.get("recording"))
    wifi_led = Led(board.leds.get("wifi"))
    usb_copier = OTCameraUsbCopier(
        power_led=power_led,
        wifi_led=wifi_led,
        rec_led=rec_led,
        src_dir=src_dir,
        usb_flash_drive=usb_flash_drive,
        debug_mode_on=config.debug_mode_on,
    )

    power_button: PowerButton | None = None
    if config.hardware.use_buttons and "power" in board.buttons:
        power_button = PowerButton(board.buttons["power"])

    return usb_copier, power_button


def main(config: Config) -> None:
    """Start the OTCamera USB copy script."""
    setup_logging(config)

    usb_config = replace(
        config,
        hardware=replace(config.hardware, use_adc=False),
    )
    board = BoardProvider.provide(usb_config)
    usb_copier: OTCameraUsbCopier | None = None
    mounted = False
    try:
        usb_copier, power_button = build_usb_copier(usb_config, board)
        src_dir = Path(usb_config.video.dir)
        usb_device_mount = Path(usb_config.usb_mount_point)
        dest_dir = usb_device_mount / get_hostname()
        usb_copy_info_path = CopyInformation.get_copy_info_csv(dest_dir)

        usb_copier.mount_usb_device()
        mounted = True
        if usb_copy_info_path.exists():
            usb_copy_info = CopyInformation.from_csv(
                usb_copy_info_path,
                src_dir,
                dest_dir,
            )
        else:
            usb_copy_info = CopyInformation.create_new(
                src_dir,
                dest_dir,
                usb_config.video.format,
            )

        usb_copier.copy_to_usb(usb_copy_info)
        usb_copier.delete(usb_copy_info)
        usb_copier.write_copy_info(usb_copy_info)

        if power_button is not None:
            while not power_button.shutdown_requested:
                time.sleep(0.1)
            usb_copier.shutdown()
    except Exception:
        logger.exception("USB copy failed")
    finally:
        if mounted and usb_copier is not None:
            try:
                usb_copier.unmount_usb_device()
            except Exception:
                logger.exception("Failed to unmount USB device during cleanup")
        board.close()
