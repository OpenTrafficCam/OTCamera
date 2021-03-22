import PySimpleGUIWeb as sg
from PySimpleGUIWeb.PySimpleGUIWeb import Slider
from hardware import camera
import calibration
import os
import glob
import time
import re
import numpy as np

# PySimpleGUIWeb runs only on Python 3. Legacy Python (2.7) is not supported.

# get all calibrationimages from imagefolder

files_cal = glob.glob("/home/pi/cal*.jpg")

# sorts list to display
files_cal.sort()

files_pre = glob.glob("/home/pi/pre*.jpg")

print(files_pre)


def main():

    # starting
    i = 1

    # gui layout with three columns
    # 1 taken picture
    # 2 calibration picture
    # 3 list box with list of calibration pictures

    layout = [
        [sg.Text("Open TrafficCam")],
        [
            sg.Image(
                filename=None, background_color="grey", size=(640, 480), key="-PREVIEW-"
            ),
            sg.Image(
                filename=None,
                background_color="grey",
                size=(640, 480),
                key="-CALIBRATEPICTURE-",
            ),
            sg.Listbox(
                values=files_cal,
                enable_events=True,
                size_px=(250, 480),
                key="-PICTURE_LIST-",
            ),
        ],
        [
            sg.Text("Chessboardcolumns"),
            sg.InputText("8", key="-COLUMNS-", size=(2, 1)),
            sg.Text("Chessboardrows"),
            sg.InputText("12", key="-ROWS-", size=(2, 1)),
            sg.Text("Squaresize in mm"),
            sg.InputText("35", key="-SIZE-", size=(2, 1)),
        ],
        [
            sg.Button("Take picture", key="-TAKE_PICTURE-", size_px=(150, 60)),
            sg.Button("Find chessboardcorners", key="-CALIBRATE-", size_px=(150, 60)),
            sg.Button("Undo last calibration", key="-UNDO-", size_px=(150, 60)),
            sg.Button(
                "Delete selected picture",
                key="-DELETE_SELECTED_PICTURE-",
                size_px=(150, 60),
            ),
            sg.Slider(
                range=(0, 10),
                size_px=(150, 60),
                default_value=5,
                tick_interval=1,
                key="-TIMER-",
            ),
        ],
        [
            sg.Text(
                "------------------------------------------------------------------------------------------------------------------------------"
            )
        ],
        [
            sg.Button(
                "Start calibration", key="-START_CALIBRATION-", size_px=(150, 60)
            ),
            sg.Button("Stop calibration", key="-STOP_CALIBRATION-", size_px=(150, 60)),
        ],
        [
            sg.Button(
                "Recieve coefficients", key="-GET_COEFFICENT-", size_px=(150, 60)
            ),
            sg.Button("Delete calibration", key="-DEL_CALIBRATION-", size_px=(150, 60)),
        ],
        [sg.Text("", key="-STATUSTEXT-")],
    ]

    window = sg.Window("", layout, web_port=2222, web_start_browser=True)

    # progress_bar = window.FindElement('progressbar')

    global stop

    while True:

        event, values = window.read(timeout=100)

        # reads colum and rows from input
        column_number = values["-COLUMNS-"]

        row_number = values["-ROWS-"]

        squaresize = values["-SIZE-"]

        PREVIEWPATH = "/home/pi/preview{0}.jpg".format(str(i))

        CALIBRATEPATH = "/home/pi/calibrate{0}.jpg".format(str(i))

        slider_val = values["-TIMER-"]

        if event == "-TAKE_PICTURE-":

            time.sleep(int(slider_val))

            # take preview picture
            camera.capture_calibrationpic(PREVIEWPATH)

            # show preview picture
            window["-PREVIEW-"].update(filename=PREVIEWPATH)

        elif event == "-CALIBRATE-":

            # path to save calibration pictures
            # CALIBRATEPATH = "/home/pi/calibrate{0}.jpg".format(str(i))

            # takes preview picture and draws chessboardlines for image and objpoint
            # save new image to CALIBRATEPATH

            # default value = 7,11
            if column_number == "" or row_number == "":
                column_number = 7
                row_number = 11

            else:
                column_number = int(column_number) - 1
                row_number = int(row_number) - 1

            # default value for squaresize
            if squaresize == "":
                squaresize = 0.035

            else:
                squaresize = int(squaresize) / 1000

            calibration.show_chessboard_corners(
                PREVIEWPATH, CALIBRATEPATH, column_number, row_number, squaresize
            )

            try:
                # if calibration is successful => append list of pictures
                window["-CALIBRATEPICTURE-"].update(filename=CALIBRATEPATH)

                files_cal.append(CALIBRATEPATH)

                files_pre.append(PREVIEWPATH)

                window["-PICTURE_LIST-"].update(files_cal)

                window["-STATUSTEXT-"].update("Calibration did work")

                # if calibration is successful => count up
                i += 1

            except:

                window["-CALIBRATEPICTURE-"].update(filename="Calibfirstdraft/fail.png")

                window["-STATUSTEXT-"].update("Calibration did not work")

                # updates listbox with new calibration picture
                window["-PICTURE_LIST-"].update(files_cal)

        elif event == "-UNDO-":

            try:

                window["-PICTURE_LIST-"].update([])

                window["-PICTURE_LIST-"].update(files_cal[:-1])

                # takes last calibrated, previewed picture and removes it from both lists
                if i != 1:
                    i -= 1

                CALIBRATEPATH = "/home/pi/calibrate{0}.jpg".format(str(i))

                PREVIEWPATH = "/home/pi/preview{0}.jpg".format(str(i))

                files_cal.remove(CALIBRATEPATH)

                # deletes files from os
                os.remove(CALIBRATEPATH)

                os.remove(PREVIEWPATH)

                files_pre.remove(PREVIEWPATH)

            except:
                window["-STATUSTEXT-"].update("Nothing to undo")

            try:
                # shows last calibrated picture im imagewindow
                window["-CALIBRATEPICTURE-"].update(
                    filename="/home/pi/calibrate{0}.jpg".format(str(i - 1))
                )

            except:

                window["-CALIBRATEPICTURE-"].update(filename="Calibfirstdraft/fail.png")

        elif event == "-GET_COEFFICENT-":

            if column_number == "" or row_number == "":
                column_number = 7
                row_number = 11

            else:
                column_number = int(column_number) - 1
                row_number = int(row_number) - 1

            # default value for squaresize
            if squaresize == "":
                squaresize = 0.035

            else:
                squaresize = int(squaresize) / 1000

            print(squaresize)
            print(type(squaresize))

            # loops thru the list of pictures that are good for calibration
            try:

                print("test")
                # empties list of img and objpoints
                calibration.objpoints = []  # 3d point in real world space
                calibration.imgpoints = []  # 2d points in image plane

                # eventuell ein bug oder falsch
                FIRSTIMAGE = files_pre[0]

                for file in files_pre:

                    print(file)

                    calibration.show_chessboard_corners(
                        file, CALIBRATEPATH, row_number, column_number, squaresize
                    )

                print(calibration.imgpoints)

                calibration.get_coefficients(FIRSTIMAGE)

            except:

                window["-STATUSTEXT-"].update("Nothing to recieve")

        elif event == "-PICTURE_LIST-":

            filename_selected = values["-PICTURE_LIST-"][0]

            # find i from filename
            picture_index = int(re.findall("\d+", filename_selected)[0])

            PREVIEWPATH = "/home/pi/preview{0}.jpg".format(str(picture_index))

            window["-CALIBRATEPICTURE-"].update(filename_selected)

            window["-PREVIEW-"].update(PREVIEWPATH)

        elif event == "-START_CALIBRATION-":

            # resets counter to 1
            i = 1

            # start with an empty list of img and obj points

            # empty list
            window["-PICTURE_LIST-"].update([])

            # default value = 7,11
            if column_number == "" or row_number == "":
                column_number = 7
                row_number = 11
            else:
                column_number = int(column_number) - 1
                row_number = int(row_number) - 1

            # default value for squaresize
            if squaresize == "":
                squaresize = 0.035

            else:
                squaresize = int(squaresize) / 1000

            while i <= 25:

                if event == "-STOP_CALIBRATION-":
                    print("Loop stopped")
                    break

                event, values = window.read(timeout=1000)

                PREVIEWPATH = "/home/pi/preview{0}.jpg".format(str(i))

                CALIBRATEPATH = "/home/pi/calibrate{0}.jpg".format(str(i))

                time.sleep(1)

                # take preview picture

                camera.capture_calibrationpic(PREVIEWPATH)

                # show preview picture
                window["-PREVIEW-"].update(filename=PREVIEWPATH)

                try:
                    calibration.show_chessboard_corners(
                        PREVIEWPATH,
                        CALIBRATEPATH,
                        column_number,
                        row_number,
                        squaresize,
                    )

                    window["-CALIBRATEPICTURE-"].update(filename=CALIBRATEPATH)

                    files_cal.append(CALIBRATEPATH)

                    files_pre.append(PREVIEWPATH)

                    # updates listbox with new calibration picture
                    window["-PICTURE_LIST-"].update(files_cal)

                    window["-STATUSTEXT-"].update("Calibration did work")

                    # if calibration is successful => count up

                    i += 1

                except:

                    window["-CALIBRATEPICTURE-"].update(
                        filename="Calibfirstdraft/fail.png"
                    )

                    window["-STATUSTEXT-"].update("Calibration did not work")

                if i == 10:
                    window["-STATUSTEXT-"].update("Calibration complete")

        elif event == "-DEL_CALIBRATION-":

            try:
                for file_cal in files_cal:
                    os.remove(file_cal)

                window["-PICTURE_LIST-"].update([])

            except:
                window["-STATUSTEXT-"].update("No pictures to delete")
            try:
                for file_pre in files_pre:
                    os.remove(file_pre)

            except:
                window["-STATUSTEXT-"].update("No pictures to delete")

        elif event == "-DELETE_SELECTED_PICTURE-":

            filename_selected = values["-PICTURE_LIST-"][0]

            # find i from filename
            picture_index = int(re.findall("\d+", filename_selected)[0])

            PREVIEWPATH = "/home/pi/preview{0}.jpg".format(str(picture_index))

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
