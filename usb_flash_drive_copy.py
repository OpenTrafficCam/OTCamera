from abc import ABC, abstractmethod
import csv
import re
import shutil
from signal import pause
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from gpiozero import PWMLED
from gpiozero import Button as GPIOButton

import OTCamera.config as config
import OTCamera.helpers.log as log


LED_POWER_PIN = 13
LED_WIFI_PIN = 12
LED_REC_PIN = 6
BUTTON_POWER_PIN = 17


class Subject(ABC):
    def __init__(self) -> None:
        self._observers: list[Observer] = []

    def attach(self, observer: "Observer") -> None:
        """Attach an observer to the subject."""
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: "Observer") -> None:
        """Detach an observer from the subject."""
        return self._observers.remove(observer)

    def notify(self) -> None:
        """Notify all observers subscribed to subject about an event."""
        for observer in self._observers:
            observer.update(self)


class Observer(ABC):
    """The Observer interface declaring update method used by subjects."""

    @abstractmethod
    def update(self, subject: Subject):
        """Receive update from subject."""
        pass


class IsNotADirectoryError(OSError):
    pass


class IllegalStateError(Exception):
    pass


@dataclass
class Video:
    filename: str
    path: Path
    copied: bool
    delete: bool

    @staticmethod
    def from_dict(d: dict, src: Path) -> "Video":
        filename = d["filename"]
        copied = bool(re.search(r"yes|y|true|x|ja|j", d["copied"]))
        delete = bool(re.search(r"yes|y|true|x|ja|j", d["delete"]))
        return Video(filename, src / filename, copied, delete)

    def to_dict(self) -> dict:
        return {"filename": self.filename, "copied": self.copied, "delete": self.delete}


class Led:
    def __init__(self, led: PWMLED) -> None:
        """Provides actions to interact with hardware LED.

        Args:
            led (PWMLED): Interface to hardware LED.
        """

        self._led = led

    def blink(self) -> None:
        """Led blinking action."""
        if not config.USE_LED:
            return
        self._led.blink(background=True)
        time.sleep(2)

    def turn_off(self) -> None:
        """Turn off LED."""
        if not config.USE_LED:
            return
        self._led.off()
        time.sleep(2)

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
        self.name = name.upper()
        self._button = button
        self.is_active = button.is_active
        self._check_button_is_active()
        self._register_callbacks()

    def _register_callbacks(self):
        self._button.when_activated = self.on_pressed
        self._button.when_deactivated = self.on_released
        log.write(f"Register {self.name} button callbacks.", log.LogLevel.DEBUG)

    def on_pressed(self):
        """Notifies observers about button pressed event."""
        log.write(f"{self.name} button pressed.", log.LogLevel.DEBUG)
        self._check_button_is_active()
        self.is_active = True
        self.notify()

    def on_released(self):
        """Notifies observers about button released event."""
        if not self._button.is_active:
            log.write("Power button released.", log.LogLevel.DEBUG)
            self.is_active = False
            self.notify()
            log.write("Observers have been notified", log.LogLevel.Debug)

    def _check_button_is_active(self) -> None:
        if not self._button.is_active:
            raise IllegalStateError(
                f"Illegal state detected. {self.name} button needs to be active "
                "for the script to be running"
            )


class CopyInformation:
    def __init__(
        self, videos: list[Video], csv_file: Path, src_dir: Path, dest_dir: Path
    ) -> None:
        self.videos = videos
        self.csv_file = csv_file
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self._validate_copy_info()

    def _validate_copy_info(self):
        """Validate and update video copy information with actual videos on disk."""
        for video in self.videos:
            if not video.path.exists():
                log.write(
                    (
                        f"File: '{video.path}'does not exist on OTCamera."
                        "Remove from copy information."
                    ),
                    log.LogLevel.WARNING,
                )
                self.videos.remove(video)

            if not video.path.is_file():
                log.write(
                    (
                        f"File: '{video.path}'is not a file."
                        "Remove from copy information."
                    ),
                    log.LogLevel.WARNING,
                )
                self.videos.remove(video)

    @staticmethod
    def from_csv(file: Path, src_dir: Path, dest_dir: Path) -> "CopyInformation":
        videos: list[Video] = []
        with open(file, mode="r") as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for _dict in csv_reader:
                videos.append(Video.from_dict(_dict, src_dir))

        return CopyInformation(videos, file, src_dir, dest_dir)

    @staticmethod
    def create_new(src_dir: Path, dest_dir: Path, filetype: str):
        dest_dir.mkdir(parents=True, exist_ok=True)
        copy_csv_file = Path(dest_dir, f"{get_hostname()}_usb-copy-info.csv")
        copy_csv_file.touch()

        video_filepaths = get_video_files(src_dir, filetype)
        videos: list[Video] = []

        for video_filepath in video_filepaths:
            video = Video(video_filepath.name, video_filepath, False, False)
            videos.append(video)

        return CopyInformation(videos, copy_csv_file, src_dir, dest_dir)

    def to_dict(self) -> list[dict]:
        new_videos: list[dict] = []
        for video in self.videos:
            video_dict = video.to_dict()
            new_videos.append(video_dict)
        return new_videos


class OTCameraUsbCopier(Observer):
    def __init__(
        self,
        power_led: Led,
        wifi_led: Led,
        rec_led: Led,
        src_dir: Path,
        usb_mount: Path,
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
            usb_mount (Path): path to the USB flash drive.
        """
        self.power_led = power_led
        self.wifi_led = wifi_led
        self.rec_led = rec_led
        self.src_dir = src_dir
        self.usb_mount = usb_mount

    def update(self, subject: Subject) -> None:
        if isinstance(subject, Button):
            if not subject.is_active:
                log.write("Shutdown OTCamera.")
                self.shutdown()

    def shutdown(self):
        """Shutdown OTCamera."""
        if self.usb_mount.is_mount():
            self.unmount_usb()
            log.write("Unmount USB flash drive", log.LogLevel.DEBUG)

        self._turn_off_all_leds()
        self.rec_led.blink()
        time.sleep(3)

        self.power_led.turn_off()
        self.rec_led.turn_off()

        self._turn_off_all_leds()
        log.closefile()

        if not config.DEBUG_MODE_ON:
            subprocess.call("sudo shutdown -h now", shell=True)

    def _turn_off_all_leds(self):
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
        time.sleep(3)
        log.write("Start copying files")
        for video in copy_info.videos:
            if video.copied:
                log.write(f"Video at: '{ video.path}' already copied.")
                continue

            if not video.path.exists():
                log.write(
                    f"Video at: '{ video.path}' does not exists.", log.LogLevel.WARNING
                )
                continue

            shutil.copy2(
                src=video.path,
                dst=self.usb_mount / video.filename,
            )
            video.copied = True
            log.write(f"Video: '{video.path}' copied.")
            log.write(f"Video: '{video.path}' copied.")
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
        for video in copy_info.videos:
            if not video.path.exists():
                log.write(
                    f"Video at: '{ video.path}' does not exists.", log.LogLevel.WARNING
                )
                continue
            if not video.delete:
                log.write(
                    f"Video at: '{ video.path}' not marked for deletion.",
                    log.LogLevel.WARNING,
                )
                continue

            video.path.unlink()
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

    def unmount_usb(self) -> None:
        """Unmount USB flash drive.

        The power LED being permanently turned on indicates the succesful unmount of the USB
        flash drive.
        """
        if not self.usb_mount.is_mount() and self.usb_mount.exists():
            log.write("USB flash drive already unmounted", log.LogLevel.WARNING)

        completedProcess: subprocess.CompletedProcess = subprocess.run(
            f"umount {self.usb_mount}"
        )
        if completedProcess.returncode != 0:
            log.write(f"Unable to unmount '{self.usb_mount}'!", log.LogLevel.ERROR)
        self.power_led.turn_on()


def get_video_files(dirpath: Path, filetype: str) -> list[Path]:
    if not dirpath.is_dir():
        raise IsNotADirectoryError(f"Path: '{dirpath}' is not a directory!")
    return [f for f in dirpath.iterdir() if f.is_file() and f.suffix == f".{filetype}"]


def get_hostname() -> str:
    return socket.gethostname()


def build_usb_copier(src_dir: Path, usb_mount: Path) -> OTCameraUsbCopier:
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
    usb_copier = OTCameraUsbCopier(power_led, wifi_led, rec_led, src_dir, usb_mount)
    if config.USE_BUTTONS:
        power_button = Button(
            "POWER",
            GPIOButton(BUTTON_POWER_PIN, pull_up=False, hold_time=2, hold_repeat=False),
        )
        power_button.attach(usb_copier)
        return usb_copier


def main():
    src_dir = Path(__file__).parent / "tests/data/example_videos_folder"
    usb_mount = Path(__file__).parent / "tests/data/example_usb_mount"
    usb_copy_info_path = (
        Path(__file__).parent
        / "tests/data/example_videos_folder/otcamera-dev01_usb-copy-info.csv"
    )

    if usb_copy_info_path.exists():
        usb_copy_info = CopyInformation.from_csv(usb_copy_info_path, src_dir, usb_mount)
    else:
        usb_copy_info = CopyInformation.create_new(src_dir, usb_mount, "h264")

    usb_copier = build_usb_copier(src_dir, usb_mount)

    usb_copier.copy_to_usb(usb_copy_info)
    usb_copier.delete(usb_copy_info)
    usb_copier.write_copy_info(usb_copy_info)

    if config.USE_BUTTONS:
        pause()


if __name__ == "__main__":
    main()
