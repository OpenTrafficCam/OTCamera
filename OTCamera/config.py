"""OTCamera config variables.

All the configuration of OTCamera is done here.

"""
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


import socket
import sys
from pathlib import Path

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

import yaml


def parse_user_config(config_file: str):
    """Parses the OTCamera user configuration YAML file.

    Args:
        config_file (str): The path to the user configuration YAML file.
    """
    config_file = str(Path(config_file).expanduser().resolve())
    try:
        with open(config_file, mode="rb") as f:
            user_config = yaml.load(f, Loader=SafeLoader)
    except FileNotFoundError:
        # TODO: use log module
        print("No user config found.")
        return

    module = sys.modules[__name__]
    setattr(module, "DEBUG_MODE_ON", user_config["debug_mode"]["enable"])

    try:
        section = user_config["debug_mode"]
    except KeyError:
        _print_key_err_msg("debug_mode")
    else:
        try:
            setattr(module, "DEBUG_MODE_ON", section["enable"])
        except KeyError:
            _print_key_err_msg("debug_mode.enable")

    try:
        section = user_config["relay_server"]
    except KeyError:
        _print_key_err_msg("relay_server")
    else:
        try:
            setattr(module, "USE_RELAY", section["enable"])
        except KeyError:
            _print_key_err_msg("relay_server.enable")

    try:
        section = user_config["recording"]
    except KeyError:
        _print_key_err_msg("recording")
    else:
        try:
            setattr(module, "START_HOUR", section["start_hour"])
        except KeyError:
            _print_key_err_msg("recording.start_hour")
        try:
            setattr(module, "END_HOUR", section["end_hour"])
        except KeyError:
            _print_key_err_msg("recording.end_hour")
        try:
            global INTERVAL_LENGTH
            setattr(module, "INTERVAL_LENGTH", section["interval_length"])
        except KeyError:
            _print_key_err_msg("recording.interval_length")
        try:
            setattr(module, "NUM_INTERVALS", section["num_intervals"])
        except KeyError:
            _print_key_err_msg("recording.num_invervals")
        try:
            setattr(module, "MIN_FREE_SPACE", section["min_free_space"])
        except KeyError:
            _print_key_err_msg("recording.min_free_space")

    try:
        section = user_config["camera"]
    except KeyError:
        _print_key_err_msg("camera")
    else:
        try:
            setattr(module, "FPS", section["fps"])
        except KeyError:
            _print_key_err_msg("camera.fps")
        try:
            setattr(
                module,
                "RESOLUTION",
                (section["resolution"]["width"], section["resolution"]["height"]),
            )
        except KeyError:
            _print_key_err_msg("camera.resolution.width, camera.resolution.height")
        try:
            setattr(module, "EXPOSURE_MODE", section["exposure_mode"])
        except KeyError:
            _print_key_err_msg("camera.exposure_mode")
        try:
            setattr(module, "DRC_STRENGTH", section["drc_strength"])
        except KeyError:
            _print_key_err_msg("camera.drc_strength")
        try:
            setattr(module, "ROTATION", section["rotation"])
        except KeyError:
            _print_key_err_msg("cammera.rotation")
        try:
            setattr(module, "AWB_MODE", section["awb_mode"])
        except KeyError:
            _print_key_err_msg("camera.awb_mode")
        try:
            setattr(module, "METER_MODE", section["meter_mode"])
        except KeyError:
            _print_key_err_msg("camera.meter_mode")

    try:
        section = user_config["preview"]
    except KeyError:
        _print_key_err_msg("preview")
    else:
        try:
            preview_path = str(Path(section["path"]).expanduser().resolve())
            setattr(module, "PREVIEW_PATH", preview_path)
        except KeyError:
            _print_key_err_msg("preview.path")
        try:
            setattr(module, "PREVIEW_FORMAT", section["format"])
        except KeyError:
            print("preview.format")
        try:
            setattr(module, "PREVIEW_INTERVAL", section["interval"])
        except KeyError:
            _print_key_err_msg("preview.interval")

    try:
        section = user_config["video"]
    except KeyError:
        _print_key_err_msg("video")
    else:
        try:
            video_dir = str(Path(section["dir"]).expanduser().resolve())
            setattr(module, "VIDEO_DIR", video_dir)
        except KeyError:
            _print_key_err_msg("video.dir")
        try:
            setattr(module, "VIDEO_FORMAT", section["format"])
        except KeyError:
            _print_key_err_msg("video.format")
        try:
            setattr(
                module,
                "RESOLUTION_SAVED_VIDEO_FILE",
                (section["resolution"]["width"], section["resolution"]["height"]),
            )
        except KeyError:
            print("KeyError in config file.")
            _print_key_err_msg("video.resolution.width, video.resolution.height")

        try:
            section = section["encoder"]
        except KeyError:
            _print_key_err_msg("encoder")
        else:
            try:
                setattr(module, "H264_PROFILE", section["profile"])
            except KeyError:
                _print_key_err_msg("encoder.profile")
            try:
                setattr(module, "H264_LEVEL", str(section["level"]))
            except KeyError:
                _print_key_err_msg("encoder.level")
            try:
                setattr(module, "H264_BITRATE", section["bitrate"])
            except KeyError:
                _print_key_err_msg("encoder.bitrate")
            try:
                global H264_QUALITY
                H264_QUALITY = section["quality"]
                setattr(module, "H264_QUALITY", section["quality"])
            except KeyError:
                _print_key_err_msg("encoder.quality")

    try:
        section = user_config["wifi"]
    except KeyError:
        _print_key_err_msg("wifi")
    else:
        try:
            setattr(module, "WIFI_DELAY", section["delay"])
        except KeyError:
            _print_key_err_msg("wifi.delay")

    try:
        section = user_config["leds"]
    except KeyError:
        _print_key_err_msg("leds")
    else:
        try:
            setattr(module, "USE_LED", section["enable"])
        except KeyError:
            _print_key_err_msg("leds.enable")

    try:
        section = user_config["buttons"]
    except KeyError:
        _print_key_err_msg("buttons")
    else:
        try:
            setattr(module, "USE_BUTTONS", section["enable"])
        except KeyError:
            _print_key_err_msg("buttons.enable")

    try:
        section = user_config["msteams"]
    except KeyError:
        _print_key_err_msg("msteams")
    else:
        try:
            setattr(module, "USE_MS_TEAMS_WEBHOOK", section["enable"])
        except KeyError:
            _print_key_err_msg("msteams.enable")
        try:
            setattr(module, "MS_TEAMS_WEBHOOK_URL", section["url"])
        except KeyError:
            _print_key_err_msg("msteams.url")


def _print_key_err_msg(key_name: str) -> None:
    """Print key error information to console."""
    print(f"KeyError in config file for: '{key_name}'")


def read_text_file(text_file: Path) -> str:
    """Reads the contents of a text file returns it."""
    with open(text_file, "r") as f:
        data = f.read()
    return data


# general config
DEBUG_MODE_ON = False
"""Turn debug mode on to get additional log entries."""
USE_RELAY = False
"""Enable to start and stop sshrelay.service (need's to be configured)"""

# recording config
START_HOUR = 6
"""Hour of day when to start recording."""
END_HOUR = 22
"""Hour of day when to end recording."""
INTERVAL_LENGTH = 15
"""Interval length in minutes before video splits."""
NUM_INTERVALS = 0
"""Number of full intervals to record (0=infinit)."""
MIN_FREE_SPACE = 1
"""free space in GB on sd card before old videos get deleted."""

# camera config
FPS = 20
"""Frames per Second. 10-20 should be enough."""
RESOLUTION = (1640, 1232)
"""Resolution of the camera module works internally.
Field of view could be smaller with other values."""
EXPOSURE_MODE = "nightpreview"
"""Controls the analog and digital gains."""
DRC_STRENGTH = "high"
"""Sets dynamic range compression to lighten dark areas and to darken light areas."""
ROTATION = 180
"""Rotate the whole camera image."""
AWB_MODE = "greyworld"
"""Controls the auto white balancing mode. `greyworld`
is a specific mode for NoIR modules."""
METER_MODE = "average"
"""Controls the size of the center region to adjust exposure."""

# preview settings
PREVIEW_PATH = "~/OTCamera/webfiles/preview.jpg"
"""path to save preview."""
PREVIEW_FORMAT = "jpeg"
"""Filetype of the static preview image."""
PREVIEW_INTERVAL = 5
"""Interval between two preview images in seconds."""

# video config
VIDEO_DIR = "~/videos/"
"""path to safe videofiles."""
VIDEO_FORMAT = "h264"
"""Encoding format."""
RESOLUTION_SAVED_VIDEO_FILE = (800, 600)
"""Resolution of the saved videofile, not the camera itself."""
H264_PROFILE = "high"
"""Profile used in h264 encoder."""
H264_LEVEL = "4"
"""Level used in h264 encoder."""
H264_BITRATE = 600000
"""Bitrate used in h264 encoder."""
H264_QUALITY = 30
"""Quality used in h264 encoder."""

# Wi-Fi config
WIFI_DELAY = 900
"""Delay in seconds before wifi turns off."""

# LED config
USE_LED = False
"""True if Status-LEDs are connected."""

# button config
USE_BUTTONS = False
"""True if hardware buttons are connected."""

# other config
PREFIX = socket.gethostname()
"""prefix for videoname and annotation."""
TEMPLATE_HTML_PATH = "~/OTCamera/webfiles/template.html"
"""Path to template HTML"""
INDEX_HTML_PATH = "~/OTCamera/webfiles/index.html"
"""Path to the auto generated index HTML."""
OFFLINE_HTML_PATH = "~/OTCamera/webfiles/offline.html"
"""Path to the HTML to be displayed when OTCamera is offline"""
NUM_LOG_FILES_HTML = 2
"""Number of log files to be displayed on the status website"""

# Microsoft Teams WebHook
USE_MS_TEAMS_WEBHOOK = False
"""`True` if MS Teams Webhook should be enabled. Otherwise `False`"""
MS_TEAMS_WEBHOOK_URL = None
"""The MS Teams incoming webhook URL."""
MS_TEAMS_MAX_FAILED_SEND_ATTEMPTS = 2
"""The number of max failed HTTP Requests send attempts."""

VIDEO_DIR = str(Path(VIDEO_DIR).expanduser().resolve())
PREVIEW_PATH = str(Path(PREVIEW_PATH).expanduser().resolve())
TEMPLATE_HTML_PATH = str(Path(TEMPLATE_HTML_PATH).expanduser().resolve())
INDEX_HTML_PATH = str(Path(INDEX_HTML_PATH).expanduser().resolve())
OFFLINE_HTML_PATH = str(Path(OFFLINE_HTML_PATH).expanduser().resolve())

OTCAMERA_VERSION = (
    read_text_file(Path("~/otcamera_version.txt").expanduser().resolve())
    if Path("~/otcamera_version.txt").expanduser().resolve().exists()
    else None
)
"""The OTCamera Version installed.

Will look for a file located in `~/otcamera_version.txt`.
If file is not found `OTCAMERA_VERSION` will be set to `None`
"""
