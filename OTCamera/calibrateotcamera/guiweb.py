import config
import PySimpleGUIWeb as sg
from hardware import camera
import calibration
import os
import glob
import time

# get all calibrationimages from imagefolder

files = glob.glob("/home/pi/cal*.jpg")

files.sort()


def main():

    i = 0

    # gui layout with three columns
    # 1 taken picture
    # 2 calibration picture
    # 3 list box with list of calibration pictures

    col1 = [[sg.Text("OpenTrafficCam OTCamera")],
            [sg.Image(filename=None, background_color="grey",
                      size=(640, 480), key="-PREVIEW-")],
            [sg.Button("Take picture", key="-TAKE_PICTURE-", size_px=(150, 60))],
            [sg.Button("Recieve coefficients", key="-GET_COEFFICENT-",
                       size_px=(150, 60))],
            [sg.Button("Start calibration",
                       key="-START_CALIBRATION-", size_px=(150, 60))],
            [sg.ProgressBar(10000, orientation='h', size=(20, 20), key='progressbar')],
                       
            ]

    col2 = [[sg.Text("Calibration")],
            [sg.Image(filename=None, background_color="grey",
                      size=(640, 480), key="-CALIBRATEPICTURE-")],
            [sg.Button("Find chessboardcorners", key="-CALIBRATE-", size_px=(150, 60))],
            [sg.Button("Stop calibration", key="-STOP_CALIBRATION-",
                       size_px=(150, 60))],
            [sg.Button("Delete pictures", key="-DEL_PICTURES-",
                       size_px=(150, 60))],
            [sg.Text("", key="-STATUSTEXT-")]
            ]

    col3 = [[sg.Text("List of calibrated pictures")],
            [sg.Listbox(values=files, enable_events=True,
                        size=(40, 15), key="-PICTURE_LIST-")]

            ]

    layout = [

        [
            sg.Column(col1),

            sg.Column(col2),

            sg.Column(col3),
        ]

    ]

    window = sg.Window("OpenTrafficCam", layout,
                       web_port=2222, web_start_browser=True)
    
    global stop

    while True:

        event, values = window.read()

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
            #CALIBRATEPATH = "/home/pi/calibrate{0}.jpg".format(str(i))

            # takes preview picture and draws chessboardlines for image and objpoint
            # save new image to CALIBRATEPATH

            calibration.show_chessboard_corners(PREVIEWPATH, CALIBRATEPATH)

            try:
                window["-CALIBRATEPICTURE-"].update(filename=CALIBRATEPATH)

                files.append(CALIBRATEPATH)

                print(files)

                window["-STATUSTEXT-"].update("Calibration did work")

            # if calibration is successful => count up
                i += 1

            except:

                window["-STATUSTEXT-"].update("Calibration did not work")

            # updates listbox with new calibration picture
            window["-PICTURE_LIST-"].update(files)

        elif event == "-GET_COEFFICENT-":

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
                    calibration.show_chessboard_corners(
                        PREVIEWPATH, CALIBRATEPATH)

                    window["-CALIBRATEPICTURE-"].update(
                        filename=CALIBRATEPATH)

                    files.append(CALIBRATEPATH)

                    window["-STATUSTEXT-"].update(
                        "Calibration did work")

                # if calibration is successful => count up
                    i += 1

                except:


                    window["-CALIBRATEPICTURE-"].update(filename="Calibfirstdraft/fail.png")

                    window["-STATUSTEXT-"].update(
                        "Calibration did not work")

            if event == "-STOP_CALIBRATION-":
                stop = True

        elif event == "-DEL_PICTURES-":

            try:
                for file in files:
                    os.remove(file)

                window["-PICTURE_LIST-"].update(files)
            except:

                window["-STATUSTEXT-"].update(
                    "No files to delete")


        elif event is None:
            break

    window.close()

    # print(config.CALIBRATEPICTURELIST)
    # print(calibration.imgpoints)

# BUG: whole process is killed when closing browser tab


print("Program terminating normally")

if __name__ == "__main__":
    main()
