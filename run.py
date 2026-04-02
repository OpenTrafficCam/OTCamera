"""CLI entry point for OTCamera."""

import argparse
from pathlib import Path

from OTCamera.__main__ import main as otcamera_main
from OTCamera.config import parse_user_config


def main() -> None:
    """Parse CLI arguments and run the appropriate OTCamera mode."""
    config_file = _parse_config_path()
    config = parse_user_config(config_file)

    if Path(config.usb_device).exists():
        import usb_flash_drive_copy

        usb_flash_drive_copy.main(config)
        return

    otcamera_main(config)


def _parse_config_path() -> str:
    """Parse the optional config path from the CLI."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="Absolute or relative path to the user config file.",
        required=False,
    )
    args = parser.parse_args()
    return args.config or "~/user_config.yaml"


if __name__ == "__main__":
    main()
