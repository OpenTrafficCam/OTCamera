import PySimpleGUIWeb as sg
from PySimpleGUIWeb.PySimpleGUIWeb import Slider
from hardware import camera
import calibration
from datetime import datetime
import os
import glob
import time
import re

# PySimpleGUIWeb runs only on Python 3. Legacy Python (2.7) is not supported.

# get all calibrationimages from imagefolder

# TODO: replace glob with pathlib or import function from helpers
# TODO: create path for jsonfile to be dumped (now: home pi ==> wanted: home/pi/"calibratefolder")

files_cal = glob.glob("/home/pi/cal*.jpg")

# sorts list to display
files_cal.sort()

# finds all preview pictures from home/pi

files_pre = glob.glob("/home/pi/pre*.jpg")

# lists für resolution to hand over to combolist widget in the gui
resolution_width = [1640, 1296, 800, 640]

resolution_height = [1231, 972, 600, 480]

resolution_combolist_values = [str(resolution_width[0])+"x" + str(resolution_height[0]),
                               str(resolution_width[1])+"x" +
                               str(resolution_height[1]),
                               str(resolution_width[2])+"x" +
                               str(resolution_height[2]),
                               str(resolution_width[3]) +
                               "x"+str(resolution_height[3])
                               ]


def main():

    # starting
    # counter and startnumber for picture file names
    i = 1

    # gui layout with three columns
    # 1 taken picture
    # 2 calibration picture
    # 3 list box with list of calibration pictures

    layout = [[sg.Text("Open TrafficCam")],
              [sg.Listbox(values=files_cal, enable_events=True, size_px=(250, 480), key="-PICTURE_LIST-"),
               sg.Image(filename=None, background_color="grey",
                        size=(640, 480), key="-PREVIEW-"),
               sg.Image(filename=None, background_color="grey",
                        size=(640, 480), key="-CALIBRATEPICTURE-"),
               ],
              [sg.Text("Chessboardcolumns"), sg.InputText("8", key='-COLUMNS-', size=(2, 1)),
               sg.Text("Chessboardrows"), sg.InputText(
                   "12", key='-ROWS-', size=(2, 1)),
               sg.Text("Squaresize in mm"), sg.InputText(
                   "35", key='-SIZE-', size=(2, 1)),
               sg.Text("Total number"), sg.InputText(
                   "25", key='-WANTED_NUMBER-', size=(2, 1)),
               sg.Text("Mean reprojection error"), sg.InputText(
                   "", key='-MEAN_ERROR-', size=(5, 1)),
               sg.Combo(['ZeroCam FishEye', 'HQ Cam 6mm', 'HQ Cam 16mm', 'Waveshare Raspberry Pi Camera (J) Fisheye', 'Joy-it rb-camera-ww2', 'Raspberry Pi Camera Board v2.1 Noir',
                         'Raspberry Pi Camera Board v2.1', 'RPI CAM NOIR MF', 'Joy-it 8mpcir CMOS Farb-Kameramodul', 'Raspberry Pi Camera Board v1.3'], key="-CAMERA-",),
               sg.Combo(values=resolution_combolist_values,
                        key="-RESOLUTION-", size_px=(90, 25))],


              [sg.Button("New Calibration", key="-CREATE_CALIBRATION-", size_px=(250, 25)),
               sg.Button("Take picture", key="-TAKE_PICTURE-",
                         size_px=(150, 25)),
               sg.Button("Undo last calibration",
                         key="-UNDO-", size_px=(150, 25)),
               sg.Button("Del picture",
                         key="-DELETE_SELECTED_PICTURE-", size_px=(150, 25)),
               sg.Slider(range=(0, 10), size_px=(150, 25), default_value=5, tick_interval=1, key="-TIMER-")],

              [sg.Input("Cam-ID", key="-CALIBRATION_INPUT-"),
               sg.Button("Start calibration",
                         key="-START_CALIBRATION-", size_px=(150, 25)),
               sg.Button("Stop calibration",
                         key="-STOP_CALIBRATION-", size_px=(150, 25)),
               sg.Button("Delete calibration",
                         key="-DEL_CALIBRATION-", size_px=(150, 25)),
               sg.Button("Recieve parameter", key="-GET_COEFFICENT-", size_px=(150, 25))],
              [sg.Text("", key="-STATUSTEXT-"),
               sg.Text("Current calibration: NONE", key="-CURRENTCALIBRATION-")]
              ]

    window = sg.Window("", layout,
                       web_port=2222, web_start_browser=False)

    # progress_bar = window.FindElement('progressbar')

    global stop

    while True:

        event, values = window.read(timeout=100)

        # reads values from inputs and dropdowns
        # values corresponds to uses chessboard size
        column_number = (values["-COLUMNS-"])

        row_number = (values["-ROWS-"])

        squaresize = (values["-SIZE-"])

        # droplist values for cameratype (not used yet)
        cameratype = (values["-CAMERA-"])

        # resolution for camera calibration picture
        resolution = (values["-RESOLUTION-"])

        # reads selected resolution from dropdownlist and puts it into picam useable format
        resolution_height = int("".join(i for i in resolution.split("x")[
                                1] if i.isdigit() or i == "."))
        resolution_width = int("".join(i for i in resolution.split("x")[
                               0] if i.isdigit() or i == "."))

        RESOLUTION = (resolution_width, resolution_height)

        # slider for timer to take pictures (reaches from 0 to 10; no other visual option available)
        slider_val = int(values["-TIMER-"])

        if event == "-CREATE_CALIBRATION-":
            # creates a folder with date, time, userdefined camid

            cam_id = values["-CALIBRATION_INPUT-"]

            now = datetime.now()

            current_time = now.strftime("%m%d%Y_%H:%M")

            CALIBRATIONFOLDER = cam_id+"_"+resolution+"_"+current_time

            # createfolder with previewpatch
            os.mkdir(CALIBRATIONFOLDER)

            window["-CURRENTCALIBRATION-"].update("Cam ID: "+cam_id)

            # path for preview picture, calibration picture
            PREVIEWPATH = "/home/pi/"+CALIBRATIONFOLDER + \
                "/preview{0}.jpg".format(str(i))

            CALIBRATEPATH = "/home/pi/"+CALIBRATIONFOLDER + \
                "/calibrate{0}.jpg".format(str(i))

        if event == "-TAKE_PICTURE-":
            # Picture part

            # countdown for picture
            for timertime in range(slider_val):
                window["-STATUSTEXT-"].update("COUNTDOWN: " +
                                              str(slider_val-timertime))
                time.sleep(1)

            window["-STATUSTEXT-"].update("TAKING PICTURE!")

            # take preview picture
            camera.capture_calibrationpic(PREVIEWPATH, RESOLUTION)

            # show preview picture
            window["-PREVIEW-"].update(filename=PREVIEWPATH)

            # Calibration part
            # default value for chessboard = 7,11
            if column_number == "" or row_number == "":
                column_number = 7
                row_number = 11

            else:
                column_number = int(column_number)-1
                row_number = int(row_number)-1

            # default value for chessboard squaresize
            if squaresize == "":
                squaresize = 0.035

            else:
                squaresize = int(squaresize)/1000

            # simultanisly trys to find chessboardcorner after every take-picture event
            calibration.show_chessboard_corners(
                PREVIEWPATH, CALIBRATEPATH, column_number, row_number, squaresize)

            try:
                # if calibration is successful => append list of pictures
                window["-CALIBRATEPICTURE-"].update(filename=CALIBRATEPATH)

                files_cal.append(CALIBRATEPATH)

                files_pre.append(PREVIEWPATH)

                window["-PICTURE_LIST-"].update(files_cal)

                window["-STATUSTEXT-"].update("Calibration did work")

                # updates listbox with new calibration picture
                window["-PICTURE_LIST-"].update(files_cal)

                # if calibration is successful => count up (index for next picture)
                i += 1

            except:

                window["-CALIBRATEPICTURE-"].update(
                    filename="Calibfirstdraft/fail.png")

                window["-STATUSTEXT-"].update("Calibration did not work")

        elif event == "-UNDO-":

            try:

                # deletes picturelist and updates without the deleted filename
                window["-PICTURE_LIST-"].update([])

                window["-PICTURE_LIST-"].update(files_cal[:-1])

                # takes last calibrated, previewed picture and removes it from both lists
                if i != 1:
                    i -= 1

                PREVIEWPATH = "/home/pi/"+CALIBRATIONFOLDER + \
                    "/preview{0}.jpg".format(str(i))

                CALIBRATEPATH = "/home/pi/"+CALIBRATIONFOLDER + \
                    "/calibrate{0}.jpg".format(str(i))

                files_cal.remove(CALIBRATEPATH)

                # deletes files from os
                os.remove(CALIBRATEPATH)

                os.remove(PREVIEWPATH)

                files_pre.remove(PREVIEWPATH)

            except:
                window["-STATUSTEXT-"].update(
                    "Nothing to undo")

            try:
                # shows last calibrated picture in imagewindow
                window["-CALIBRATEPICTURE-"].update(
                    filename="/home/pi/calibrate{0}.jpg".format(str(i-1)))

            except:

                window["-CALIBRATEPICTURE-"].update(
                    filename="Calibfirstdraft/fail.png")

        elif event == "-GET_COEFFICENT-":

            if column_number == "" or row_number == "":
                column_number = 7
                row_number = 11

            else:
                column_number = int(column_number)-1
                row_number = int(row_number)-1

            # default value for squaresize
            if squaresize == "":
                squaresize = 0.035

            else:
                squaresize = int(squaresize)/1000

            # loops thru the list of pictures that are good for calibration
            try:

                # empties list of img and objpoints
                calibration.objpoints = []  # 3d point in real world space
                calibration.imgpoints = []  # 2d points in image plane

                # eventuell ein bug oder falsch
                FIRSTIMAGE = files_pre[0]

                # finds chessboard corner from all previewpic
                # caluculates coefficient and dumps parameters
                for file in files_pre:

                    calibration.show_chessboard_corners(
                        file, CALIBRATEPATH, row_number, column_number, squaresize)

                # insert mean projection error

                reprojection_error = calibration.get_coefficients(
                    FIRSTIMAGE)

                reprojection_error_rounded = round(reprojection_error, 2)

                window["-MEAN_ERROR-"].update(str(reprojection_error_rounded))

            except:

                window["-STATUSTEXT-"].update("Nothing to recieve")

        # display chosen picture and calibration picture when selected in listbox
        elif event == "-PICTURE_LIST-":

            try:
                filename_selected = values["-PICTURE_LIST-"][0]

                # find i from filename
                picture_index = int(re.findall("\d+", filename_selected)[0])

                PREVIEWPATH = "/home/pi/"+CALIBRATIONFOLDER + \
                    "/preview{0}.jpg".format(
                        str(picture_index))

                window["-CALIBRATEPICTURE-"].update(filename_selected)

                window["-PREVIEW-"].update(PREVIEWPATH)

            except:

                window["-STATUSTEXT-"].update(
                    "Can not find File, pls reload window")

        elif event == "-START_CALIBRATION-":
            # automatically keeps taking and calibrating pictures till a wanted number is met
            # counter is implemented

            window["-PICTURE_LIST-"].update([])

            # resets counter to 1
            i = 1

            calibrationpicture_maxnumber = values["-WANTED_NUMBER-"]

            if calibrationpicture_maxnumber == '':

                calibrationpicture_maxnumber = 25

            # convert string to int
            calibrationpicture_maxnumber = int(calibrationpicture_maxnumber)

            # start with an empty list of img and obj points

            # empty list
            window["-PICTURE_LIST-"].update([])

            # default value = 7,11
            if column_number == "" or row_number == "":
                column_number = 7
                row_number = 11
            else:
                column_number = int(column_number)-1
                row_number = int(row_number)-1

            # default value for squaresize 35 mm
            if squaresize == "":
                squaresize = 0.035

            else:
                squaresize = int(squaresize)/1000

            while i <= calibrationpicture_maxnumber:

                if event == "-STOP_CALIBRATION-":
                    print("Loop stopped")
                    break

                event, values = window.read(timeout=1000)

                PREVIEWPATH = "/home/pi/"+CALIBRATIONFOLDER + \
                    "/preview{0}.jpg".format(str(i))

                CALIBRATEPATH = "/home/pi/"+CALIBRATIONFOLDER + \
                    "/calibrate{0}.jpg".format(str(i))

                # countdown for picture
                for timertime in range(slider_val):
                    window["-STATUSTEXT-"].update("COUNTDOWN: " +
                                                  str(slider_val-timertime))
                    time.sleep(1)

                window["-STATUSTEXT-"].update("TAKING PICTURE!")

                camera.capture_calibrationpic(PREVIEWPATH, RESOLUTION)

                # show preview picture
                window["-PREVIEW-"].update(filename=PREVIEWPATH)

                try:
                    calibration.show_chessboard_corners(
                        PREVIEWPATH, CALIBRATEPATH, column_number, row_number, squaresize)

                    window["-CALIBRATEPICTURE-"].update(
                        filename=CALIBRATEPATH)

                    files_cal.append(CALIBRATEPATH)

                    files_pre.append(PREVIEWPATH)

                    # updates listbox with new calibration picture
                    window["-PICTURE_LIST-"].update(files_cal)

                    window["-STATUSTEXT-"].update(
                        "Calibration did work")

                # if calibration is successful => count up

                    i += 1

                except:

                    window["-CALIBRATEPICTURE-"].update(
                        filename="Calibfirstdraft/fail.png")

                    window["-STATUSTEXT-"].update(
                        "Calibration did not work")

                if i == 10:
                    window["-STATUSTEXT-"].update(
                        "Calibration complete")

        elif event == "-DEL_CALIBRATION-":

            try:
                for file_cal in files_cal:
                    os.remove(file_cal)

                window["-PICTURE_LIST-"].update([])

            except:
                window["-STATUSTEXT-"].update(
                    "No pictures to delete")

            try:
                for file_pre in files_pre:
                    os.remove(file_pre)

            except:
                window["-STATUSTEXT-"].update(
                    "No pictures to delete")

            window["-PICTURE_LIST-"].update([])

            i = 1

        elif event == "-DELETE_SELECTED_PICTURE-":

            filename_selected = values["-PICTURE_LIST-"][0]

            # find i from filename
            picture_index = int(re.findall("\d+", filename_selected)[0])

            PREVIEWPATH = "/home/pi/"+CALIBRATIONFOLDER + \
                "/preview{0}.jpg".format(str(picture_index))

            files_cal.remove(filename_selected)

            files_pre.remove(PREVIEWPATH)

            # deletes files from os
            os.remove(filename_selected)

            os.remove(PREVIEWPATH)

            window["-PICTURE_LIST-"].update([])

            window["-PICTURE_LIST-"].update(files_cal)

        elif event is None:
            break

    window.close()

    # print(config.CALIBRATEPICTURELIST)
    # print(calibration.imgpoints)

# BUG: whole process is killed when closing browser tab


print("Program terminating normally")

if __name__ == "__main__":
    main()
