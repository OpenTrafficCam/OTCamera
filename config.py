import socket

# Turn debug mode on to get addition log entries
DEBUG = True

# Hour of day when to start/end recording
STARTHOUR = 8
ENDHOUR = 22
# Interval length in minutes before video splits
INTERVAL = 3
# Number of full intervals to record (0=infinit)
# Number of full intervals to record (0=infinit)
N_INTERVALS = 1

# prefix for videoname and annotation
PREFIX = socket.gethostname()
# path to safe videofiles
VIDEOPATH = "/home/pi/videos/"
# path to save preview
PREVIEWPATH = "/home/pi/preview.jpg"

PARAMETER_DICT = {"AWB_MODE": ["auto","sunlight","cloudy","shade","tungsten","horizon"],
                    "BRIGHTNESS":[50,40,60], 
                    "CONTRAST":[0,-25,25], 
                    "DRC_STRENGTH":["off","low","medium", "high"], 
                    "EXPOSURE_COMPENSATION":[0,-10,10], 
                    "EXPOSURE_MODE":["auto"], 
                    "VIDEO_DENOISE":[True, False], 
                   "METER_MODE":["average", "backlit","matrix"],           
                  }  

# camera settings
FPS = 30
BITRATE = 600000
QUALITY = 30
ROTATION = 0
RESOLUTION = (1640, 1232)

AWB_MODE = "AWB_MODE"
BRIGHTNESS = "BRIGHTNESS"
CONTRAST = "CONTRAST"
DRC_STRENGTH = "DRC_STRENGTH"
EXPOSURE_COMPENSATION = "EXPOSURE_COMPENSATION"
EXPOSURE_MODE = "EXPOSURE_MODE"
VIDEO_DENOISE = "VIDEO_DENOISE"
METER_MODE =  "METER_MODE"



# video settings
FORMAT = "h264"
PREVIEWFORMAT = "jpeg"
RESIZE = (800, 600)



