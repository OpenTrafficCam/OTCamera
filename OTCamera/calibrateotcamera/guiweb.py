import config
import PySimpleGUIWeb as sg
from hardware import camera
import calibration
import os
import glob
import time

# get all calibrationimages from imagefolder

files_cal = glob.glob("/home/pi/cal*.jpg")

files_cal.sort()

files_pre = glob.glob("/home/pi/pre*.jpg")


def main():

    i = 0

    # gui layout with three columns
    # 1 taken picture
    # 2 calibration picture
    # 3 list box with list of calibration pictures

    layout = [
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
                size=(40, 18),
                key="-PICTURE_LIST-",
            ),
        ],
        [
            sg.Button("Take picture", key="-TAKE_PICTURE-", size_px=(150, 60)),
            sg.Button("Find chessboardcorners", key="-CALIBRATE-", size_px=(150, 60)),
        ],
        [sg.Text("-------------------------------------------------------------")],
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
            sg.Button("Delete pictures", key="-DEL_PICTURES-", size_px=(150, 60)),
        ],
        [sg.Text("", key="-STATUSTEXT-")],
    ]

    window = sg.Window("OpenTrafficCam", layout, web_port=2222, web_start_browser=True)

    # progress_bar = window.FindElement('progressbar')

    global stop

    while True:

        event, values = window.read(timeout=10)

        PREVIEWPATH = "/home/pi/preview{0}.jpg".format(str(i))

        CALIBRATEPATH = "/home/pi/calibrate{0}.jpg".format(str(i))

        if event == "-TAKE_PICTURE-":
            print("tada")

            # take preview picture

            camera.capture_calibrationpic(PREVIEWPATH)

            # show preview picture
            window["-PREVIEW-"].update(filename=PREVIEWPATH)

        elif event == "-CALIBRATE-":

            # path to save calibration pictures
            # CALIBRATEPATH = "/home/pi/calibrate{0}.jpg".format(str(i))

            # takes preview picture and draws chessboardlines for image and objpoint
            # save new image to CALIBRATEPATH

            calibration.show_chessboard_corners(PREVIEWPATH, CALIBRATEPATH)

            try:
                window["-CALIBRATEPICTURE-"].update(filename=CALIBRATEPATH)

                files_cal.append(CALIBRATEPATH)

                print(files_cal)

                window["-STATUSTEXT-"].update("Calibration did work")

                # if calibration is successful => count up
                i += 1

            except:

                window["-STATUSTEXT-"].update("Calibration did not work")

            # updates listbox with new calibration picture
            window["-PICTURE_LIST-"].update(files_cal)

        elif event == "-GET_COEFFICENT-":

            # eventuell ein bug oder falsch
            FIRSTIMAGE = "/home/pi/preview0.jpg"

            calibration.get_coefficients(FIRSTIMAGE)

        elif event == "-PICTURE_LIST-":

            filename = values["-PICTURE_LIST-"][0]

            window["-CALIBRATEPICTURE-"].update(filename=filename)

        elif event == "-START_CALIBRATION-":

            while i <= 10:

                if event == "-STOP_CALIBRATION-":
                    print("Loop stopped")
                    break

                event, values = window.read(timeout=1000)

                print(i)

                PREVIEWPATH = "/home/pi/preview{0}.jpg".format(str(i))

                CALIBRATEPATH = "/home/pi/calibrate{0}.jpg".format(str(i))

                time.sleep(1)

                # take preview picture

                camera.capture_calibrationpic(PREVIEWPATH)

                # show preview picture
                window["-PREVIEW-"].update(filename=PREVIEWPATH)

                try:
                    calibration.show_chessboard_corners(PREVIEWPATH, CALIBRATEPATH)

                    window["-CALIBRATEPICTURE-"].update(filename=CALIBRATEPATH)

                    files_cal.append(CALIBRATEPATH)

                    # updates listbox with new calibration picture
                    window["-PICTURE_LIST-"].update(files_cal)

                    window["-STATUSTEXT-"].update("Calibration did work")

                    # if calibration is successful => count up
                    i += 1

                    # progress_bar.UpdateBar(i*1)

                except:

                    window["-CALIBRATEPICTURE-"].update(
                        filename="Calibfirstdraft/fail.png"
                    )

                    window["-STATUSTEXT-"].update("Calibration did not work")

            if i == 10:
                window["-STATUSTEXT-"].update("Calibration complete")

        elif event == "-DEL_PICTURES-":

            try:
                for file in files_cal:
                    os.remove(file)

                for file in files_pre:
                    os.remove(file)

                window["-PICTURE_LIST-"].update(files_cal)
            except:

                window["-STATUSTEXT-"].update("No pictures to delete")

        elif event is None:
            break

    window.close()

    # print(config.CALIBRATEPICTURELIST)
    # print(calibration.imgpoints)


# BUG: whole process is killed when closing browser tab


print("Program terminating normally")

if __name__ == "__main__":
    main()
