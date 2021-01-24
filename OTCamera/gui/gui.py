import config
import PySimpleGUIWeb as sg
from hardware import camera


def main():
    layout = [
        [sg.Text("OpenTrafficCam OTCamera")],
        [sg.Image(filename=config.PREVIEWPATH, key="preview")],
        [sg.Button("New Preview", key="previewbutton")],
    ]

    window = sg.Window("OpenTrafficCam", layout)
    i = 0
    while True:
        event, values = window.read()
        if event == "previewbutton":
            print("tada")
            camera.preview(now=True)
            window["preview"].update(filename=config.PREVIEWPATH)
        if event is None:
            break
        i += 1
    window.close()


print("Program terminating normally")
