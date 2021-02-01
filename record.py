import status
import camera
import config
from time import sleep


def loop():
    # if true dann start recording
    if status.record_time():
        camera.start_recording()
        camera.split_if_interval_ends()
        camera.wait_recording(0.5)
    else:
        camera.stop_recording()
        sleep(0.5)

def record():
    try:

        while status.more_intervals:
            loop()


    except (KeyboardInterrupt):
        print("interrupted")

    camera.stop_recording()



if __name__ == "__main__":

    for setting in config.PARAMETER_DICT[config.AWB_MODE]:
        camera.default_settings()
        status.interval_finished = False
        status.more_intervals = True
        status.current_interval = 0
        camera.picam.awb_mode = setting
        print(setting)
        record()
        
    for setting in config.PARAMETER_DICT[config.BRIGHTNESS][1:]:
        camera.default_settings()
        status.interval_finished = False
        status.more_intervals = True
        status.current_interval = 0
        camera.picam.brightness = setting
        print(setting)
        record()

    for setting in config.PARAMETER_DICT[config.CONTRAST][1:]:
        camera.default_settings()
        status.interval_finished = False
        status.more_intervals = True
        status.current_interval = 0
        camera.picam.contrast = setting
        print(setting)
        record()

    for setting in config.PARAMETER_DICT[config.DRC_STRENGTH][1:]:
        camera.default_settings()
        status.interval_finished = False
        status.more_intervals = True
        status.current_interval = 0
        camera.picam.drc_strength = setting
        print(setting)
        record()

    for setting in config.PARAMETER_DICT[config.EXPOSURE_COMPENSATION][1:]:
        camera.default_settings()
        status.interval_finished = False
        status.more_intervals = True
        status.current_interval = 0
        camera.picam.exposure_compensation = setting
        print(setting)
        record()
 
    for setting in config.PARAMETER_DICT[config.EXPOSURE_MODE][1:]:
        camera.default_settings()
        status.interval_finished = False
        status.more_intervals = True
        status.current_interval = 0
        camera.picam.exposure_mode = setting
        print(setting)
        record()

    for setting in config.PARAMETER_DICT[config.VIDEO_DENOISE][1:]:
        camera.default_settings()
        status.interval_finished = False
        status.more_intervals = True
        status.current_interval = 0
        camera.picam.video_denoise = setting
        print(setting)
        record()

    for setting in config.PARAMETER_DICT[config.METER_MODE][1:]:
        camera.default_settings()
        status.interval_finished = False
        status.more_intervals = True
        status.current_interval = 0
        camera.picam.meter_mode = setting
        print(setting)
        record()



