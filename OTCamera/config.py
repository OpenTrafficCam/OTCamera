"""OTCamera config variables.

All the configuration of OTCamera is done here.

"""
# Copyright (C) 2021 OpenTrafficCam Contributors
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
from pathlib import Path

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

import yaml

# general config
DEBUG_MODE_ON = True
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

VIDEO_DIR = str(Path(VIDEO_DIR).expanduser().resolve())
PREVIEW_PATH = str(Path(PREVIEW_PATH).expanduser().resolve())
TEMPLATE_HTML_PATH = str(Path(TEMPLATE_HTML_PATH).expanduser().resolve())
INDEX_HTML_PATH = str(Path(INDEX_HTML_PATH).expanduser().resolve())
OFFLINE_HTML_PATH = str(Path(OFFLINE_HTML_PATH).expanduser().resolve())


def parse_user_config(config_file: str = "./user_config.yaml"):

    try:
        with open(config_file, mode="rb") as f:
            user_config = yaml.load(f, Loader=SafeLoader)
    except FileNotFoundError:
        # TODO: use log module
        print("Config file not found.")
        return

    try:
        section = user_config["debug_mode"]
    except KeyError:
        print("KeyError in config file.")
        pass
    else:
        try:
            global DEBUG_MODE_ON
            DEBUG_MODE_ON = section["enable"]
        except KeyError:
            pass

    try:
        section = user_config["relay_server"]
    except KeyError:
        print("KeyError in config file.")
        pass
    else:
        try:
            global USE_RELAY
            USE_RELAY = section["enable"]
        except KeyError:
            pass

    try:
        section = user_config["recording"]
    except KeyError:
        print("KeyError in config file.")
        pass
    else:
        try:
            global START_HOUR
            START_HOUR = section["start_hour"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global END_HOUR
            END_HOUR = section["end_hour"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global INTERVAL_LENGTH
            INTERVAL_LENGTH = section["interval_length"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global NUM_INTERVALS
            NUM_INTERVALS = section["num_intervals"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global MIN_FREE_SPACE
            MIN_FREE_SPACE = section["min_free_space"]
        except KeyError:
            print("KeyError in config file.")
            pass

    try:
        section = user_config["camera"]
    except KeyError:
        print("KeyError in config file.")
        pass
    else:
        try:
            global FPS
            FPS = section["fps"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global RESOLUTION
            RESOLUTION = (
                section["resolution"]["width"],
                section["resolution"]["height"],
            )
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global EXPOSURE_MODE
            EXPOSURE_MODE = section["exposure_mode"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global DRC_STRENGTH
            DRC_STRENGTH = section["drc_strength"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global ROTATION
            ROTATION = section["rotation"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global AWB_MODE
            AWB_MODE = section["awb_mode"]
        except KeyError:
            print("KeyError in config file.")
            pass

    try:
        section = user_config["preview"]
    except KeyError:
        print("KeyError in config file.")
        pass
    else:
        try:
            global PREVIEW_PATH
            PREVIEW_PATH = section["path"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global PREVIEW_FORMAT
            PREVIEW_FORMAT = section["format"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global PREVIEW_INTERVAL
            PREVIEW_INTERVAL = section["interval"]
        except KeyError:
            print("KeyError in config file.")
            pass

    try:
        section = user_config["video"]
    except KeyError:
        print("KeyError in config file.")
        pass
    else:
        try:
            global VIDEO_DIR
            VIDEO_DIR = section["dir"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global VIDEO_FORMAT
            VIDEO_FORMAT = section["format"]
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            global RESOLUTION_SAVED_VIDEO_FILE
            RESOLUTION_SAVED_VIDEO_FILE = (
                section["resolution"]["width"],
                section["resolution"]["height"],
            )
        except KeyError:
            print("KeyError in config file.")
            pass
        try:
            section = section["encoder"]
        except KeyError:
            print("KeyError in config file.")
            pass
        else:
            try:
                global H264_PROFILE
                H264_PROFILE = section["profile"]
            except KeyError:
                print("KeyError in config file.")
                pass
            try:
                global H264_LEVEL
                H264_LEVEL = section["level"]
            except KeyError:
                print("KeyError in config file.")
                pass
            try:
                global H264_BITRATE
                H264_BITRATE = section["bitrate"]
            except KeyError:
                print("KeyError in config file.")
                pass
            try:
                global H264_QUALITY
                H264_QUALITY = section["quality"]
            except KeyError:
                print("KeyError in config file.")
                pass

    try:
        section = user_config["wifi"]
    except KeyError:
        print("KeyError in config file.")
        pass
    else:
        try:
            global WIFI_DELAY
            WIFI_DELAY = section["delay"]
        except KeyError:
            pass

    try:
        section = user_config["leds"]
    except KeyError:
        print("KeyError in config file.")
        pass
    else:
        try:
            global USE_LED
            USE_LED = section["enable"]
        except KeyError:
            pass

    try:
        section = user_config["buttons"]
    except KeyError:
        print("KeyError in config file.")
        pass
    else:
        try:
            global USE_BUTTONS
            USE_BUTTONS = section["enable"]
        except KeyError:
            pass


parse_user_config("./user_config.yaml")
