import config
import PySimpleGUIWeb as sg
from hardware import camera
import calibration
import os
import glob

#get all calibrationimages from imagefolder

files= glob.glob("/home/pi/cal*.jpg")



def main():

    i = 0

    # gui layout with three columns 
    #1 taken picture 
    #2 calibration picture 
    #3 list box with list of calibration pictures

    col1 = [[sg.Text("OpenTrafficCam OTCamera")],
            [sg.Image(filename=None,background_color ="grey", size = (640, 480), key="-PREVIEW-")],
            [sg.Button("Take picture", key="-TAKE_PICTURE-")],
            [sg.Button("get coefficients", key="-GET_COEFFICENT-")],
        ]

    col2 = [[sg.Text("Calibration")],
            [sg.Image(filename=None,background_color ="grey", size = (640, 480) ,key="-CALIBRATEPICTURE-")],
            [sg.Button("calibrate", key="-CALIBRATE-")], [sg.Text("", key="-STATUSTEXT-")]
            ]

    col3 = [[sg.Text("List of calibrated pictures")],
            [sg.Listbox( values=files, enable_events=True, size=(40, 15), key="-PICTURE_LIST-")]

    ]

    layout = [
                
            [
                sg.Column(col1), 

                sg.VSeperator(),

                sg.Column(col2),

                sg.Column(col3),
            ]

            ]

    window = sg.Window("OpenTrafficCam", layout)

    i = 0

    while True:

        event, values = window.read()

        if event == "-TAKE_PICTURE-":
            print("tada")

            #take preview picture

            camera.capture_calibrationpic()

            # show preview picture
            window["-PREVIEW-"].update(filename=config.PREVIEWPATH)



        elif event == "-CALIBRATE-":


            # path to save calibration pictures
            CALIBRATEPATH = "/home/pi/calibrate{0}.jpg".format(str(i))

            # takes preview picture and draws chessboardlines for image and objpoint
            # save new image to CALIBRATEPATH
            calibration.show_chessboard_corners(CALIBRATEPATH)

            try:
                window["-CALIBRATEPICTURE-"].update(filename=CALIBRATEPATH)

                files.append(CALIBRATEPATH)

                window["-STATUSTEXT-"].update("Calibration did work")

            except:

                window["-STATUSTEXT-"].update("Calibration did not work")

            i += 1

            # updates listbox with new calibration picture
            window["-PICTURE_LIST-"].update(files)


        elif event == "-GET_COEFFICENT-":

            calibration.get_coefficients()

        elif event == "-PICTURE_LIST-": 

            filename = values["-PICTURE_LIST-"][0]


            window["-CALIBRATEPICTURE-"].update(filename=filename)

        if event is None:
            break
    window.close()

    # print(config.CALIBRATEPICTURELIST)
    # print(calibration.imgpoints)

# BUG: whole process is killed when closing browser tab

print("Program terminating normally")

if __name__ == "__main__":
    main()