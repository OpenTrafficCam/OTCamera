import csv
import re
import shutil
import socket
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from gpiozero import PWMLED
from gpiozero import Button as GPIOButton

import OTCamera.config as config
import OTCamera.helpers.log as log

COPY_INFO_CSV_SUFFIX = "_usb-copy-info.csv"
LED_POWER_PIN: int = 13
LED_WIFI_PIN: int = 12
LED_REC_PIN: int = 6
BUTTON_POWER_PIN: int = 17


class Subject(ABC):
    @abstractmethod
    def attach(self, observer: "Observer") -> None:
        """Attach an observer to the subject."""
        pass

    @abstractmethod
    def detach(self, observer: "Observer") -> None:
        """Detach an observer from the subject."""
        pass

    @abstractmethod
    def notify(self) -> None:
        """Notify all observers subscribed to subject about an event."""
        pass


class Observer(ABC):
    """The Observer interface declaring update method used by subjects."""

    @abstractmethod
    def update(self, is_active: bool) -> None:
        """Receive update from subject.

        Args:
            subject (Subject): the subject.
            is_active (bool): whether the subject is active
        """
        pass


class IsNotADirectoryError(OSError):
    pass


class IllegalStateError(Exception):
    pass


class UsbFlashDriveNotMountableError(Exception):
    pass


class UsbFlashDriveUnmountableError(Exception):
    pass


@dataclass
class Video:
    filename: str
    path: Path
    copied: bool
    delete: bool

    @staticmethod
    def from_dict(data: dict, src: Path) -> "Video":
        filename = data["filename"]
        copied = bool(re.search(r"yes|y|true|x|ja|j", data["copied"].lower()))
        delete = bool(re.search(r"yes|y|true|x|ja|j", data["delete"].lower()))
        return Video(filename, src / filename, copied, delete)

    def __hash__(self) -> int:
        return hash(self.path)

    def to_dict(self) -> dict:
        return {"filename": self.filename, "copied": self.copied, "delete": self.delete}

    def __eq__(self, __o: object) -> bool:
        """
        A `Video` object is equal to another Video object if their path is the
        same.
        """
        if not isinstance(__o, Video):
            return NotImplemented
        return self.path == __o.path


class Led:
    def __init__(self, led: PWMLED) -> None:
        """Provides actions to interact with hardware LED.

        Args:
            led (PWMLED): Interface to hardware LED.
        """

        self._led = led

    def blink(self, times: Union[int, None] = None, background: bool = True) -> None:
        """Led blinking action.

        Args:
            times (Union[int, None], optional): Number of times to blink.
            Defaults to `None` meaning forever.
            background (bool, optional): Start as background thread.
            If `False` return only when blink has finished when `n!=None`.
            Defaults to `True`.
        """
        if not config.USE_LED:
            return
        self._led.blink(n=times, background=background)
        time.sleep(2)

    def turn_off(self) -> None:
        """Turn off LED."""
        if not config.USE_LED:
            return
        self._led.off()

    def turn_on(self) -> None:
        """Turn on LED."""
        if not config.USE_LED:
            return
        self._led.on()
        time.sleep(2)


class Button(Subject):
    def __init__(self, name: str, button: GPIOButton) -> None:
        """Automatically notifies list of observers of button state changes.

        Args:
            name (str): The name of the button.
            button (GPIOButton): Interface to physical hardware button.
        """
        super().__init__()
        self._observers: list[Observer] = []
        self.name = name.upper()
        self._button = button
        self.is_active = self._button.is_active
        self._check_button_is_active()
        self._register_callbacks()

    def attach(self, observer: "Observer") -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: "Observer") -> None:
        return self._observers.remove(observer)

    def notify(self) -> None:
        for observer in self._observers:
            observer.update(self.is_active)

    def _register_callbacks(self) -> None:
        self._button.when_deactivated = self.on_released
        log.write(f"Register {self.name} button callbacks.", log.LogLevel.DEBUG)

    def on_released(self) -> None:
        """Notifies observers about button released event."""
        log.write("Power button released.", log.LogLevel.DEBUG)
        self.is_active = False
        self.notify()
        log.write("Observers have been notified", log.LogLevel.DEBUG)

    def _check_button_is_active(self) -> None:
        if not self._button.is_active:
            raise IllegalStateError(
                f"Illegal state detected. {self.name} button needs to be active "
                "for the script to be running"
            )


class CopyInformation:
    def __init__(
        self, videos: set[Video], csv_file: Path, src_dir: Path, dest_dir: Path
    ) -> None:
        self.videos = videos
        self.csv_file = csv_file
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self._validate_copy_info()

    def _validate_copy_info(self) -> None:
        """Validate and update video copy information with actual videos on disk."""
        videos_on_src = self._get_videos_from_src()

        for video in self.videos.copy():
            if not video.path.exists():
                log.write(
                    (
                        f"File: '{video.path}' does not exist on OTCamera. "
                        "Remove from copy information."
                    ),
                    log.LogLevel.WARNING,
                )
                self.remove(video)
                continue

            videos_on_src.discard(video)

            if Path(self.dest_dir, video.filename).exists():
                video.copied = True
                log.write(
                    f"Video '{video.filename}' already copied. Set copied=True.",
                    log.LogLevel.DEBUG,
                )
        # Videos remaining in videos_on_src are new ones
        self.videos.update(videos_on_src)

    def _get_videos_from_src(self) -> set[Video]:
        videos_on_src: set[Video] = set()
        for video_path in get_video_files(self.src_dir, "h264"):
            videos_on_src.add(
                Video(video_path.name, video_path, copied=False, delete=False)
            )
        return videos_on_src

    def remove(self, video: Video) -> None:
        """Remove video from videos list."""
        self.videos.discard(video)

    def get_sorted_videos(self) -> list[Video]:
        """Get sorted list of videos by filename."""
        return sorted(self.videos, key=lambda video: video.filename)

    def to_dict(self) -> list[dict]:
        serialized_videos: list[dict] = []
        for video in self.get_sorted_videos():
            video_dict = video.to_dict()
            serialized_videos.append(video_dict)
        return serialized_videos

    @staticmethod
    def from_csv(file: Path, src_dir: Path, dest_dir: Path) -> "CopyInformation":
        videos: set[Video] = set()
        with open(file, mode="r") as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for _dict in csv_reader:
                videos.add(Video.from_dict(_dict, src_dir))

        return CopyInformation(videos, file, src_dir, dest_dir)

    @staticmethod
    def get_copy_info_csv(directory: Path) -> Path:
        """Get the location of the copy information CSV file of this OTCamera."""
        return Path(directory, f"{get_hostname()}{COPY_INFO_CSV_SUFFIX}")

    @staticmethod
    def create_new(src_dir: Path, dest_dir: Path, filetype: str) -> "CopyInformation":
        dest_dir.mkdir(parents=True, exist_ok=True)
        copy_csv_file = CopyInformation.get_copy_info_csv(dest_dir)
        copy_csv_file.touch()

        video_filepaths = get_video_files(src_dir, filetype)
        videos: set[Video] = set()

        for video_filepath in video_filepaths:
            video = Video(video_filepath.name, video_filepath, False, False)
            videos.add(video)

        return CopyInformation(videos, copy_csv_file, src_dir, dest_dir)


@dataclass
class UsbFlashDrive:
    """Wrapper to usb flash drives providing mount and unmount function.

    IMPORTANT: Requires an entry in /etc/fstab to give user permission to access
    usb mount device.

    `self.mount_point` must be the same as in /etc/fstab.

    Raises:
        UsbFlashDriveNotMountableError: If not able to mount usb flash drive.
    """

    mount_point: Path

    def mount(self) -> None:
        """Mount USB flash drive.

        IMPORTANT: Requires an entry in /etc/fstab to give user permission to access
        usb mount device.

        `self.mount_point` must be the same as in /etc/fstab.
        """
        if self.mount_point.is_mount():
            log.write("USB flash drive already mounted", log.LogLevel.WARNING)
            return

        self.mount_point.mkdir(parents=True, exist_ok=True)

        return_code: int = subprocess.call(f"sudo mount {self.mount_point}", shell=True)
        if return_code != 0:
            raise UsbFlashDriveNotMountableError(
                (f"Unable to mount USB flash drive to '{self.mount_point}'!",)
            )
        log.write("USB flash drive mounted.")

    def unmount(self) -> None:
        """Unmount USB flash drive."""
        if not self.mount_point.is_mount():
            log.write("USB flash drive already unmounted", log.LogLevel.WARNING)
            return

        return_code: int = subprocess.call(
            f"sudo umount {self.mount_point}", shell=True
        )
        if return_code != 0:
            raise UsbFlashDriveUnmountableError(
                f"Unable to unmount USB flash drive from '{self.mount_point}'!"
            )
        log.write("USB flash drive unmounted.")


class OTCameraUsbCopier(Observer):
    def __init__(
        self,
        power_led: Led,
        wifi_led: Led,
        rec_led: Led,
        src_dir: Path,
        usb_flash_drive: UsbFlashDrive,
    ) -> None:
        """This classes' main purpose is to provide methods to copy and delete videos
        with the help of a `CopyInformation` object.

        Args:
            power_led (Led): give user visual feedback to inform about the current
            status of the OTCameraUsbCopier.
            wifi_led (Led): give user visual feedback to inform about the current
            status of the OTCameraUsbCopier.
            rec_led (Led): give user visual feedback to inform about the current
            status of the OTCameraUsbCopier.
            src_dir (Path): directory where the video files to be copied are located at.
            usb_flash_drive (UsbFlashdrive): The USB flash drive.
        """
        self.power_led = power_led
        self.wifi_led = wifi_led
        self.rec_led = rec_led
        self.src_dir = src_dir
        self.usb_flash_drive = usb_flash_drive
        self.shutdown_requested = False

    def update(self, is_active: bool) -> None:
        self.shutdown_requested = not is_active

    def shutdown(self) -> None:
        """Shutdown OTCamera."""

        self._turn_off_all_leds()
        self.power_led.blink(times=4, background=False)

        self.power_led.turn_on()

        if not config.DEBUG_MODE_ON:
            log.closefile()
            subprocess.call("sudo shutdown -h now", shell=True)

    def _turn_off_all_leds(self) -> None:
        """Turn off all LEDs."""
        self.power_led.turn_off()
        self.wifi_led.turn_off()
        self.rec_led.turn_off()

    def copy_to_usb(self, copy_info: CopyInformation) -> None:
        """Copy over videos to USB flash drive.

        The WiFi LED blinking indicates the videos being copied over.
        The WiFi LED constantly being on indicates that the copy process is finished.

        Args:
            copy_info (CopyInformation): the copy information.
        """
        self.wifi_led.blink()
        log.write("Start copying files")
        for video in copy_info.videos:
            if video.copied:
                log.write(f"Video at: '{ video.path}' already copied. Skipping.")
                continue

            if not video.path.exists():
                log.write(
                    f"Video at: '{ video.path}' does not exists.", log.LogLevel.WARNING
                )
                continue
            try:
                shutil.copy2(
                    src=video.path,
                    dst=copy_info.dest_dir / video.filename,
                )
                video.copied = True
                log.write(f"Video: '{video.path}' copied.")
                log.write(f"Video: '{video.path}' copied.")
            except IOError:
                log.write(
                    f"Unable to copy video '{video.path}'.",
                    level=log.LogLevel.EXCEPTION,
                )
        log.write("Copying over videos to USB flash drive finished.")
        self.wifi_led.turn_on()

    def delete(self, copy_info: CopyInformation) -> None:
        """Delete videos marked for deletion on OTCamera.

        The recording LED blinking indicates the videos being deleted.
        The recording LED constantly being on indicates that the delete process has
        finished.

        Args:
            copy_info (CopyInformation): The copy information.
        """
        self.rec_led.blink()
        for video in copy_info.videos.copy():
            if not video.path.exists():
                log.write(
                    f"Video at: '{ video.path}' does not exist.", log.LogLevel.WARNING
                )
                copy_info.remove(video)
                continue
            if not video.delete:
                log.write(
                    f"Video at: '{ video.path}' not marked for deletion. Skipping.",
                )
                continue

            if config.DEBUG_MODE_ON:
                log.write("Debug mode on. Only mock deleting file.", log.LogLevel.DEBUG)
            else:
                try:
                    video.path.unlink()
                    copy_info.remove(video)
                except FileNotFoundError:
                    log.write(
                        f"Video '{video.path}' could not be found although it should "
                        "exist.",
                        log.LogLevel.EXCEPTION,
                    )

                    pass
                except IOError:
                    log.write(
                        f"Error occurred while trying to delete video '{video.path}'.",
                        level=log.LogLevel.EXCEPTION,
                    )

            log.write(f"Video at: '{video.path}' deleted!")
        self.rec_led.turn_on()

    def write_copy_info(self, copy_info: CopyInformation) -> None:
        """Writes or overwrites an existing copy information csv.

        Args:
            copy_info (CopyInformation): The copy information.
        """
        with open(copy_info.csv_file, "w", newline="") as csv_file:
            writer = csv.DictWriter(
                csv_file, fieldnames=["filename", "copied", "delete"]
            )
            writer.writeheader()
            for video_info in copy_info.to_dict():
                writer.writerow(video_info)

    def mount_usb_device(self) -> None:
        # """Mount USB flash drive."""
        self.usb_flash_drive.mount()

    def unmount_usb_device(self) -> None:
        """Unmount USB flash drive.

        The power LED being permanently turned on indicates the succesful unmount of
        the USB flash drive.
        """
        self.usb_flash_drive.unmount()
        self.power_led.turn_on()


def get_video_files(directory: Path, filetype: str) -> list[Path]:
    if not directory.is_dir():
        raise IsNotADirectoryError(f"Path: '{directory}' is not a directory!")
    return [
        file
        for file in directory.iterdir()
        if file.is_file() and file.suffix == f".{filetype}"
    ]


def get_hostname() -> str:
    return socket.gethostname()


def build_usb_copier(src_dir: Path, usb_mount_point: Path) -> OTCameraUsbCopier:
    """Builds a `OTCameraUsbCopier` object.

    Args:
        src_dir (Path): directory where the video files to be copied are located at.
        usb_mount (Path): path to the USB flash drive.

    Returns:
        OTCameraUsbCopier: The usb copier object.
    """
    power_led = Led(PWMLED(LED_POWER_PIN))
    rec_led = Led(PWMLED(LED_REC_PIN))
    wifi_led = Led(PWMLED(LED_WIFI_PIN))
    usb_flash_drive = UsbFlashDrive(usb_mount_point)
    usb_copier = OTCameraUsbCopier(
        power_led, wifi_led, rec_led, src_dir, usb_flash_drive
    )
    if config.USE_BUTTONS:
        power_button = Button(
            "POWER",
            GPIOButton(BUTTON_POWER_PIN, pull_up=False, hold_time=2, hold_repeat=False),
        )
        power_button.attach(usb_copier)
    return usb_copier


def main(
    video_dir: str,
    mount_point: str,
) -> None:
    """Start the OTCamera USB copy script.

    Args:
        video_dir (str, optional): Folder containing videos.
        mount_point (str, optional): The USB device's mount point.

    Raises:
        UsbFlashDriveNotMountableError: If USB flash drive is not mountable.
    """
    usb_device_mount = Path(mount_point)
    src_dir: Path = Path(video_dir)
    dest_dir: Path = Path(usb_device_mount, get_hostname())
    usb_copier = build_usb_copier(src_dir, usb_device_mount)
    usb_copy_info_path = CopyInformation.get_copy_info_csv(dest_dir)

    try:
        usb_copier.mount_usb_device()
        if usb_copy_info_path.exists():
            usb_copy_info = CopyInformation.from_csv(
                usb_copy_info_path, src_dir, dest_dir
            )
        else:
            usb_copy_info = CopyInformation.create_new(src_dir, dest_dir, "h264")

        usb_copier.copy_to_usb(usb_copy_info)
        usb_copier.delete(usb_copy_info)
        usb_copier.write_copy_info(usb_copy_info)
        usb_copier.unmount_usb_device()

        if config.USE_BUTTONS:
            while not usb_copier.shutdown_requested:
                continue
            usb_copier.shutdown()

    except Exception as e:
        log.write(str(e), log.LogLevel.EXCEPTION)
