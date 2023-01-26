import csv
import logging
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
import time
from signal import pause

from gpiozero import PWMLED

LED_POWER_PIN = 13
LED_REC_PIN = 6


class IsNotADirectoryError(OSError):
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
        self._led = led

    def blink(self) -> None:
        self._led.blink(background=True)
        time.sleep(2)

    def turn_off(self) -> None:
        self._led.off()
        time.sleep(2)

    def turn_on(self) -> None:
        self._led.on()
        time.sleep(2)


@dataclass
class CopyInformation:
    videos: list[Video]
    csv_file: Path
    src_dir: Path
    dest_dir: Path

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
        new_videos: list[Video] = []
        for video in self.videos:
            video_dict = video.to_dict()
            new_videos.append(video_dict)
        return new_videos


class OTCameraUsbCopier:
    def __init__(
        self,
        rec_led: Led,
        power_led: Led,
        src_dir: Path,
        usb_mount: Path,
    ) -> None:
        self.rec_led = rec_led
        self.power_led = power_led
        self.src_dir = src_dir
        self.usb_mount = usb_mount

    def copy_over_usb(self, copy_info: CopyInformation) -> None:
        self.rec_led.blink()
        time.sleep(5)
        print("Start copying files")
        for video in copy_info.videos:
            if video.copied:
                logging.info(f"Video at: '{ video.path}' already copied.")
                continue

            if not video.path.exists():
                logging.warning(f"Video at: '{ video.path}' does not exists.")
                continue

            shutil.copy2(
                src=video.path,
                dst=self.usb_mount / video.filename,
            )
            video.copied = True
            logging.info(f"Video: '{video.path}' copied.")
            print(f"Video: '{video.path}' copied.")
        self.rec_led.turn_off()
        self.power_led.blink()

    def delete(self, copy_info: CopyInformation) -> None:
        for video in copy_info.videos:
            if not video.path.exists():
                logging.warning(f"Video at: '{ video.path}' does not exists.")
                continue
            if not video.delete:
                logging.warning(f"Video at: '{ video.path}' not marked for deletion.")
                continue

            video.path.unlink()
            logging.info(f"Video at: '{video.path}' deleted!")

    def update(self, copy_info: CopyInformation) -> None:
        with open(copy_info.csv_file, "w", newline="") as csv_file:
            writer = csv.DictWriter(
                csv_file, fieldnames=["filename", "copied", "delete"]
            )
            writer.writeheader()
            for video_info in copy_info.to_dict():
                writer.writerow(video_info)

    def unmount_usb(self) -> None:
        completedProcess: subprocess.CompletedProcess = subprocess.run(
            f"umount {self.usb_mount}"
        )
        if completedProcess.returncode != 0:
            logging.error(f"Unable to unmount '{self.usb_mount}'!")
        self.power_led.turn_on()


def get_video_files(dirpath: Path, filetype: str) -> list[Path]:
    if not dirpath.is_dir():
        raise IsNotADirectoryError(f"Path: '{dirpath}' is not a directory!")
    return [f for f in dirpath.iterdir() if f.is_file() and f.suffix == f".{filetype}"]


def get_hostname() -> str:
    return socket.gethostname()


def main():
    src_dir = Path(__file__).parent / "tests/data/example_videos_folder"
    usb_mount = Path(__file__).parent / "tests/data/example_usb_mount"
    logging.basicConfig(filename=src_dir / "log", encoding="utf-8")
    usb_copy_info_path = (
        Path(__file__).parent
        / "tests/data/example_videos_folder/otcamera-dev01_usb-copy-info.csv"
    )

    if usb_copy_info_path.exists():
        usb_copy_info = CopyInformation.from_csv(usb_copy_info_path, src_dir, usb_mount)
    else:
        usb_copy_info = CopyInformation.create_new(src_dir, usb_mount, "h264")

    power_led = Led(PWMLED(LED_POWER_PIN))
    rec_led = Led(PWMLED(LED_REC_PIN))
    usb_copier = OTCameraUsbCopier(rec_led, power_led, src_dir, usb_mount)
    usb_copier.copy_over_usb(usb_copy_info)
    usb_copier.update(usb_copy_info)
    pause()


if __name__ == "__main__":
    main()
