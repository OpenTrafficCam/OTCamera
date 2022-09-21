import argparse
import sys
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


def main():
    parse_args()

    import OTCamera.record as record

    record.main()


if __name__ == "__main__":
    module = sys.modules[__name__]
    main()
