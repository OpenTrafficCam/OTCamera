#!/usr/bin/env python


import datetime as dt
import os
import traceback
from subprocess import call
from time import sleep

import picamera
import psutil
from gpiozero import PWMLED, Button

print("QuerCam")
DEBUG_ON = False

# INTERVAL = 15 #minutes
# FPS = 20
# PROFILE = 'high'
# LEVEL = '4'
# BITRATE = 600000
# QUALITY = 30

# RESOLUTION = (1640, 1232)
# RESIZE = (800, 600)
# HOSTNAME = os.uname()[1]
# MINFREESPACE = 1 #GB
# VIDEOPATH = '/home/pi/videos/'
# PREVIEWPATH = '/home/pi/webfiles/preview.jpg'

# STARTHOUR = 6
# ENDHOUR = 22

# POWERPIN = 6
# HOURPIN = 19
# WIFIPIN = 16
# LOWBATTERYPIN = 18
# POWERLEDPIN = 13
# WIFILEDPIN = 12
# RECLEDPIN = 5

# WIFIDELAY = 900 #sec

# global WIFIAPON
# WIFIAPON = True

# global SHUTDOWNACTIVE
# SHUTDOWNACTIVE = False

# global NOBLINK
# NOBLINK = False


# def get_filename():
#     filename = (
#         VIDEOPATH
#         + HOSTNAME
#         + "_"
#         + dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#         + ".h264"
#     )
#     return filename


# def get_logfilename():
#     filename = (
#         VIDEOPATH
#         + HOSTNAME
#         + "_"
#         + dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#         + ".log"
#     )
#     return filename


# def current_time_str():
#     time_str = dt.datetime.now().strftime(HOSTNAME + " %d.%m.%Y %H:%M:%S")
#     return time_str


# def print_date(msg, reboot=True):
#     try:
#         if msg == "#":
#             msg = "############################"
#             print(msg)
#             logfile.write(msg + "\n")
#         else:
#             msg = "%s: " % dt.datetime.now() + msg
#             print(msg)
#             logfile.write(msg + "\n")
#         logfile.flush()
#     except:
#         print("PRINT AND LOG NOT POSSIBLE")
#         if reboot:
#             reboot_rpi()


# def delete_old_files():
#     enough_space = psutil.disk_usage("/").free > MINFREESPACE * 1024 * 1024 * 1024
#     while not enough_space:
#         try:
#             oldest_video = min(os.listdir(VIDEOPATH), key=os.path.getctime)
#             os.remove(VIDEOPATH + oldest_video)
#             print_date("#")
#             print_date("Deleted " + oldest_video)
#         except:
#             print_date("#")
#             print_date("ERROR: Cannot delete file")
#             reboot_rpi()
#         enough_space = psutil.disk_usage("/").free > MINFREESPACE * 1024 * 1024 * 1024


# def lowbattery():
#     global SHUTDOWNACTIVE
#     global NOBLINK
#     try:
#         print_date("Low Battery", False)
#         if camera.recording:
#             camera.stop_recording()
#             print_date("Stop record", False)
#         print_date("#", False)
#         print_date("Shutdown", False)
#         print_date("#", False)
#         logfile.close()
#     except:
#         print_date("ERROR: Low Battery error", False)
#     finally:
#         call("sudo shutdown -h -t 0", shell=True)


# def shutdown_rpi():
#     global SHUTDOWNACTIVE
#     global NOBLINK
#     try:
#         print_date("Shutdown by button in 2s", False)
#         NOBLINK = True
#         powerled.blink(
#             on_time=0.5,
#             off_time=0.5,
#             fade_in_time=0,
#             fade_out_time=0,
#             n=8,
#             background=False,
#         )
#         powerled.on()
#         wifiled.off()
#         # sleep(2)
#         if power_switch.is_pressed:
#             NOBLINK = False
#             print_date("Shutdown cancelled", False)
#             return
#         else:
#             SHUTDOWNACTIVE = True
#             try:
#                 if camera.recording:
#                     camera.stop_recording()
#                     recled.off()
#                     camera.close()
#                     print_date("Stop record", False)
#             except:
#                 print_date("No camera", False)
#             print_date("#", False)
#             print_date("Shutdown", False)
#             print_date("#", False)
#             logfile.close()
#     except:
#         print_date("ERROR: Shutdown error", False)
#         SHUTDOWNACTIVE = False
#     call("sudo shutdown -h -t 0", shell=True)


# def reboot_rpi():
#     global SHUTDOWNACTIVE
#     global NOBLINK
#     try:
#         SHUTDOWNACTIVE = True
#         NOBLINK = True
#         powerled.blink(
#             on_time=0.1,
#             off_time=0.1,
#             fade_in_time=0,
#             fade_out_time=0,
#             n=None,
#             background=True,
#         )
#         traceback.print_exc(file=logfile)
#         logfile.write("\n")
#         print_date("Reboot", False)
#         print_date("#", False)
#         logfile.close()
#         camera.close()
#     except:
#         print_date("ERROR: Reboot error", False)
#     finally:
#         sleep(1)
#         print("Finally reboot")
#         if not DEBUG_ON:
#             call("sudo reboot", shell=True)


# def its_record_time():
#     current_hour = dt.datetime.now().hour
#     record_time = (
#         (hour_switch.is_pressed)
#         or (current_hour >= STARTHOUR and current_hour < ENDHOUR)
#     ) and (not SHUTDOWNACTIVE)
#     return record_time


# def wifi():
#     global WIFIAPON
#     try:
#         print_date("Wifiswitch")
#         if wifi_switch.is_pressed and not WIFIAPON:
#             print_date("Turn WifiAP on")
#             call("sudo /bin/bash /usr/local/bin/wifistart", shell=True)
#             print_date("WifiAP on")
#             powerled.pulse(fade_in_time=0.25, fade_out_time=0.25, n=2, background=True)
#             wifiled.blink(on_time=0.1, off_time=4.9, n=None, background=True)
#             WIFIAPON = True
#         elif not wifi_switch.is_pressed and WIFIAPON:
#             powerled.pulse(fade_in_time=0.25, fade_out_time=0.25, n=2, background=True)
#             if not DEBUG_ON:
#                 sleep(WIFIDELAY)
#             if not wifi_switch.is_pressed and WIFIAPON:
#                 print_date("Turn WifiAP OFF")
#                 call(
#                     "sudo systemctl stop hostapd.service && sudo systemctl stop dnsmasq.service",
#                     shell=True,
#                 )
#                 call("sudo ifconfig uap0 down", shell=True)
#                 print_date("WifiAP OFF")
#                 wifiled.off()
#                 WIFIAPON = False
#     except:
#         print_date("#")
#         print_date("ERROR: Wifi Switch not possible")
#         reboot_rpi()


# def hour_switched():
#     if hour_switch.is_pressed:
#         print_date("Hour Switch pressed")
#     elif not hour_switch.is_pressed:
#         print_date("Hour Switch released")


# def preview_on():
# return WIFIAPON


try:
    logfile = open(get_logfilename(), "a")
    print_date("#")
    print_date("#")
    print_date("#")
    print_date("Started script")

    powerled = PWMLED(POWERLEDPIN)
    wifiled = PWMLED(WIFILEDPIN)
    recled = PWMLED(RECLEDPIN)
    powerled.on()
    wifiled.on()
    recled.on()

    delete_old_files()

    lowbattery_switch = Button(
        LOWBATTERYPIN, pull_up=True, hold_time=2, hold_repeat=False
    )
    power_switch = Button(POWERPIN, pull_up=False, hold_time=2, hold_repeat=False)
    hour_switch = Button(HOURPIN, pull_up=True, hold_time=2, hold_repeat=False)
    wifi_switch = Button(WIFIPIN, pull_up=True, hold_time=2, hold_repeat=False)
    lowbattery_switch.when_held = lowbattery
    power_switch.when_released = shutdown_rpi
    wifi_switch.when_held = wifi
    wifi_switch.when_released = wifi
    hour_switch.when_pressed = hour_switched
    hour_switch.when_released = hour_switched
    print_date("Buttons connected")

    wifiled.blink(on_time=0.1, off_time=4.9, n=None, background=True)
    wifi()

    # camera = picamera.PiCamera()
    # camera.framerate = FPS
    # camera.resolution = RESOLUTION
    # camera.annotate_background = picamera.Color("black")
    # camera.annotate_text = current_time_str()
    # camera.exposure_mode = "nightpreview"
    # camera.drc_strength = "high"
    # camera.rotation = 180
    # print_date("Camera ready")
    new_interval = False
    new_preview = True

    powerled.off()
    recled.off()

    while True:

        current_second = dt.datetime.now().second
        if (current_second % 5) == 0:
            if not NOBLINK:
                powerled.blink(on_time=0.1, off_time=0, n=1, background=True)

        if its_record_time():
            camera.annotate_text = current_time_str()
            current_minute = dt.datetime.now().minute

            if not camera.recording:
                try:
                    delete_old_files()
                    camera.start_recording(
                        get_filename(),
                        format="h264",
                        resize=RESIZE,
                        profile=PROFILE,
                        level=LEVEL,
                        bitrate=BITRATE,
                        quality=QUALITY,
                    )
                    print_date("Started record")
                    if not NOBLINK:
                        recled.blink(on_time=0.1, off_time=4.9, n=None, background=True)
                    camera.wait_recording(2)
                    camera.capture(
                        PREVIEWPATH, format="jpeg", resize=RESIZE, use_video_port=True
                    )
                    print_date("Captured Preview")
                except:
                    print_date("#")
                    print_date("ERROR: Start record not possible")
                    reboot_rpi()

            if (current_minute % INTERVAL) == 0 and new_interval:
                if DEBUG_ON:
                    print_date("New interval")
                try:
                    camera.split_recording(get_filename())
                    powerled.pulse(
                        fade_in_time=0.25, fade_out_time=0.25, n=2, background=True
                    )
                    delete_old_files()
                    print_date("Split")
                except (picamera.exc.PiCameraRuntimeError):
                    print_date("#")
                    print_date("ERROR: PiCamera Runtime Error")
                    reboot_rpi()
                except:
                    print_date("#")
                    print_date("ERROR: Split not possible")
                    reboot_rpi()
                new_interval = False
            elif ((current_minute + 1) % INTERVAL) == 0 and not new_interval:
                new_interval = True
                if DEBUG_ON:
                    print_date("Reset new_interval")
            if (current_second % 5) == 4 and new_preview and preview_on():
                if DEBUG_ON:
                    print_date("Start Preview")
                try:
                    camera.capture(
                        PREVIEWPATH,
                        format="jpeg",
                        resize=(640, 480),
                        use_video_port=True,
                    )
                    if DEBUG_ON:
                        print_date("Captured Preview")
                except:
                    print_date("#")
                    print_date("ERROR: Capture Preview not possible")
                finally:
                    new_preview = False
            elif ((current_second - 1) % 5) == 4 and not new_preview and preview_on():
                new_preview = True
                if DEBUG_ON:
                    print_date("Reset new_preview")

        else:
            try:
                if camera.recording:
                    camera.stop_recording()
                    recled.off()
                    recled.pulse(
                        fade_in_time=0.25, fade_out_time=0.25, n=4, background=True
                    )
                    print_date("Stopped")
            except:
                print_date("#")
                print_date("ERROR: Cant stop recording")
                reboot_rpi()
        try:
            if camera.recording:
                camera.wait_recording(0.5)
            else:
                sleep(1)
        except (KeyboardInterrupt):
            raise
        except:
            print_date("#")
            print_date("ERROR: Cant sleep or wait for record")
            reboot_rpi()

except (KeyboardInterrupt):
    if camera.recording:
        camera.stop_recording()
    camera.close()
    print_date("Stopped")
    logfile.close()

except:
    reboot_rpi()
