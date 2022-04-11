# 'import config, status
# import PySimpleGUIWeb as sg
# from time import sleep


# def main():
#     #camera.preview(now=True)


#     layout = [
#         [sg.Text("OpenTrafficCam OTCamera")],
#         [sg.Image(filename=None, key="preview")],
#         [sg.Button("New Preview", key="previewbutton")],
#     ]

#     window = sg.Window(
#         "OpenTrafficCam",
#         layout,
#         element_padding=(5, 5),
#         web_port=2222,
#         web_start_browser=True,
#         disable_close=True,
#         auto_size_buttons=False,
#     )
#     i = 0
#     while True:
#         event, values = window.read()
#         if event == "previewbutton":
#               print("tada")
#               window["preview"].update(filename=config.PREVIEWPATH)
#         #window["preview"].update(filename=config.PREVIEWPATH)
#         if event is None:
#             break
#         i += 1
#     window.close()
#     print("Program terminating normally")
'
