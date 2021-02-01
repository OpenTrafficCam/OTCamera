from datetime import datetime as dt
import config
import camera


def video():
    """
    Path incl. filename where videos are saved to, based on hostname and
    current date and time.

    Returns:
        str: filename for video
    """

    filename = current_dt() +" AWB_MODE "+ camera.picam.awb_mode +" BRIGHTNESS "+ str(camera.picam.brightness) +" CONTRAST "+ str(camera.picam.contrast) +" DRC_STRENGTH "+ camera.picam.drc_strength +" EXPOSURE_COMPENSATION "+str(camera.picam.exposure_compensation) +" EXPOSURE_MODE "+ camera.picam.exposure_mode +" VIDEO_DENOISE "+ str(camera.picam.video_denoise) +" METER_MODE "+ camera.picam.meter_mode + ".h264"
    return filename



def annotate():
    """
    Text to be added as annotation to video footage.

    Returns:
        str: annotation text
    """

    time_str = dt.now().strftime(config.PREFIX + " %d.%m.%Y %H:%M:%S")
    return time_str


# TODO: refactor time stuff in separate helper
def current_dt():
    """
    Generates current date and time.

    Returns:
        str: YYYY-mm-dd_HH-MM-SS
    """

    curr_dt = dt.now().strftime("%Y-%m-%d_%H-%M-%S")
    return curr_dt


def current_t():
    """
    Generates current time.

    Returns:
        str: HH-MM-SS
    """

    curr_t = dt.now().strftime("%H-%M-%S")
    return curr_t


def preview():
    """
    Path incl. filename where preview file is saved.

    Returns:
        str: filename for preview
    """
    return config.PREVIEWPATH


if __name__ == "__main__":
    config.VIDEOPATH = "local test video"
    config.PREFIX = "local test host"

    print("video: {str}".format(str=video()))
    print("annotate: {str}".format(str=annotate()))
    print("current_dt: {str}".format(str=current_dt()))
