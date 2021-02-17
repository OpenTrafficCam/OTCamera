"""OTCamera main module to record videos.

This module can be used to record either some intervals or continuously.
It is configured by py.

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


from time import sleep

import picamera
from helpers import log, name
from hardware import camera
import config
from datetime import datetime as dt


# Dictionary with settingparameters to test. 
# Key = parameter
# valuelist to loop over

PARAMETER_DICT = {"AWB_MODE": ["auto","sunlight","cloudy","shade","tungsten","horizon"],
                    "BRIGHTNESS":[50, 40,60], 
                    "CONTRAST":[0,-25,25], 
                    "DRC_STRENGTH":["off","low","medium", "high"], 
                    "EXPOSURE_COMPENSATION":[0,-10,10], 
                    "EXPOSURE_MODE":["auto"], 
                    "VIDEO_DENOISE":[True, False], 
                   "METER_MODE":["average", "backlit","matrix"],           
                  }  


AWB_MODE = "AWB_MODE"
BRIGHTNESS = "BRIGHTNESS"
CONTRAST = "CONTRAST"
DRC_STRENGTH = "DRC_STRENGTH"
EXPOSURE_COMPENSATION = "EXPOSURE_COMPENSATION"
EXPOSURE_MODE = "EXPOSURE_MODE"
VIDEO_DENOISE = "VIDEO_DENOISE"
METER_MODE =  "METER_MODE"

# first initialization of settings

camera.picam.awb_mode = PARAMETER_DICT[AWB_MODE][0]
camera.picam.brightness = PARAMETER_DICT[BRIGHTNESS][0]
camera.picam.contrast = PARAMETER_DICT[CONTRAST][0]
camera.picam.drc_strength = PARAMETER_DICT[DRC_STRENGTH][0]
camera.picam.exposure_compensation = PARAMETER_DICT[EXPOSURE_COMPENSATION][0]
camera.picam.exposure_mode = PARAMETER_DICT[EXPOSURE_MODE][0]
camera.picam.video_denoise = PARAMETER_DICT[VIDEO_DENOISE][0]
camera.picam.meter_mode = PARAMETER_DICT[METER_MODE][0]


def video():
    """
    Path incl. filename where videos are saved to, used settings

    Returns:
        str: filename for video
    """

    filename = " AWB_MODE "+ camera.picam.awb_mode +" BRIGHTNESS "+ str(camera.picam.brightness) +" CONTRAST "+ str(camera.picam.contrast) +" DRC_STRENGTH "+ camera.picam.drc_strength +" EXPOSURE_COMPENSATION "+str(camera.picam.exposure_compensation) +" EXPOSURE_MODE "+ camera.picam.exposure_mode +" VIDEO_DENOISE "+ str(camera.picam.video_denoise) +" METER_MODE "+ camera.picam.meter_mode + ".h264"
    return filename


def record():
    """
    records video for 60 sec
    """

    camera.picam.start_recording(video())
    camera.picam.wait_recording(60)
    camera.picam.stop_recording()


loopbool = True


if __name__ == "__main__":
    # loop over different settings, defined in the parameter dictionary
    # loop starts when timecritera from status.py is met
    # loop ends wenn last setting is test.

    while loopbool == True:
        current_hour = dt.now().hour
        bytime = current_hour >= config.STARTHOUR and current_hour < config.ENDHOUR
        print(bytime)
        if bytime:
            for setting in PARAMETER_DICT[AWB_MODE]:
                camera.picam.awb_mode = setting
                print(setting)
                record()
                
            for setting in PARAMETER_DICT[BRIGHTNESS][1:]:
                camera.picam.brightness = setting
                print(setting)
                record()

            for setting in PARAMETER_DICT[CONTRAST][1:]:
                camera.picam.contrast = setting
                print(setting)
                record()

            for setting in PARAMETER_DICT[DRC_STRENGTH][1:]:
                camera.picam.drc_strength = setting
                print(setting)
                record()

            for setting in PARAMETER_DICT[EXPOSURE_COMPENSATION][1:]:
                camera.picam.exposure_compensation = setting
                print(setting)
                record()
        
            for setting in PARAMETER_DICT[EXPOSURE_MODE][1:]:
                camera.picam.exposure_mode = setting
                print(setting)
                record()

            for setting in PARAMETER_DICT[VIDEO_DENOISE][1:]:
                camera.picam.video_denoise = setting
                print(setting)
                record()

            for setting in PARAMETER_DICT[METER_MODE][1:]:
                camera.picam.meter_mode = setting
                print(setting)
                record()
            loopbool = False
        else:
            sleep(60)

