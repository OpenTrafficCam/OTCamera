import picamera
from datetime import datetime as dt
from time import sleep
import config
import status
import name

#defaultsettings
picam = picamera.PiCamera()
picam.framerate = config.FPS
picam.resolution = config.RESOLUTION
picam.annotate_background = picamera.Color("black")
picam.annotate_text = name.annotate()

#default to-change settings

picam.awb_mode = config.PARAMETER_DICT[config.AWB_MODE][0]
picam.brightness = config.PARAMETER_DICT[config.BRIGHTNESS][0]
picam.contrast = config.PARAMETER_DICT[config.CONTRAST][0]
picam.drc_strength = config.PARAMETER_DICT[config.DRC_STRENGTH][0]
picam.exposure_compensation = config.PARAMETER_DICT[config.EXPOSURE_COMPENSATION][0]
picam.exposure_mode = config.PARAMETER_DICT[config.EXPOSURE_MODE][0]
picam.video_denoise = config.PARAMETER_DICT[config.VIDEO_DENOISE][0]
picam.meter_mode = config.PARAMETER_DICT[config.METER_MODE][0]



picam.rotation = config.ROTATION

def default_settings():
    picam.awb_mode = config.PARAMETER_DICT[config.AWB_MODE][0]
    picam.brightness = config.PARAMETER_DICT[config.BRIGHTNESS][0]
    picam.contrast = config.PARAMETER_DICT[config.CONTRAST][0]
    picam.drc_strength = config.PARAMETER_DICT[config.DRC_STRENGTH][0]
    picam.exposure_compensation = config.PARAMETER_DICT[config.EXPOSURE_COMPENSATION][0]
    picam.exposure_mode = config.PARAMETER_DICT[config.EXPOSURE_MODE][0]
    picam.video_denoise = config.PARAMETER_DICT[config.VIDEO_DENOISE][0]
    picam.meter_mode = config.PARAMETER_DICT[config.METER_MODE][0]



def start_recording():
    # TODO: exception handling
    if not picam.recording:
        picam.annotate_text = name.annotate()
        # beginns with recording
        picam.start_recording(
            # filename
            output=name.video(),
            #..
            format=config.FORMAT,
            #..
            resize=config.RESIZE,
        )
        wait_recording(2)
    else:
        pass

def wait_recording(timeout=0):
    if picam.recording:
        picam.wait_recording(timeout)
    else:
        sleep(timeout)

def split_if_interval_ends():
    if new_interval():
        picam.split_recording(name.video())
        status.interval_finished = False
        status.current_interval += 1
        if config.N_INTERVALS > 0:
            status.more_intervals = status.current_interval < config.N_INTERVALS
    elif after_new_interval():
        status.interval_finished = True


def stop_recording():
    if picam.recording:
        picam.stop_recording()

def new_interval():
    new_interval = (
        interval_minute() and status.interval_finished and status.more_intervals
    )
    # if remainer of minutes and intervall zero 
    return new_interval

def interval_minute():
    current_minute = dt.now().minute
    interval_minute = (current_minute % config.INTERVAL) == 0 
    return interval_minute


def after_new_interval():
    after_new_interval = not (interval_minute() or status.interval_finished)
    return after_new_interval


