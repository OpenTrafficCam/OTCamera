# Copyright (C) 2023 OpenTrafficCam Contributors
# <https://github.com/OpenTrafficCam>
# <team@opentrafficcam.org>

# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A

# PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import os
from pathlib import Path

import OTCamera.config as config


def parse_args() -> Path:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="the absolute path to your custom config file.",
        required=False,
    )
    args = parser.parse_args()

    if args.config is not None and not Path(args.config).exists():
        raise FileNotFoundError(f"The user config '{args.config}' does not exist.")

    if args.config:
        config.parse_user_config(args.config)
    else:
        config.parse_user_config("~/user_config.yaml")


def usb_device_exists(usb_device: str) -> bool:
    """Whether a usb device at `usb_device` exists."""

    return Path(usb_device).exists()


def main():
    parse_args()
    usb_device = "/dev/sda1"
    user_name = os.getlogin()
    usb_mount_point = f"/home/{user_name}/mnt/usb"

    if usb_device_exists(usb_device):
        import usb_flash_drive_copy

        usb_flash_drive_copy.main(config.VIDEO_DIR, usb_mount_point)
    else:
        import OTCamera.record as record

        record.main()


if __name__ == "__main__":
    main()
