import config
from record import record
from hardware import camera
import remi.gui as gui
from remi import start, App
from time import sleep
from helpers.rpi import start_accesspoint

class MyApp(App):
    def __init__(self, *args):
        super(MyApp, self).__init__(*args)

    def main(self):
        container = gui.VBox(width=1000, height=800)
        self.bt1 = gui.Button('preview')
        self.bt2 = gui.Button('record')
        self.image = gui.Image(r"/res:"+config.PREVIEWPATH)

        # setting the listener for the onclick event of the button
        self.bt1.onclick.do(self.on_button1_pressed)
        self.bt2.onclick.do(self.on_button2_pressed)


        # appending a widget to another, the first argument is a string key
        container.append(self.image)
        container.append(self.bt1)
        container.append(self.bt2)

        # returning the root widget
        return container

    # listener function
    def on_button1_pressed(self, widget):
        camera.preview(now=True)
        self.image.set_image(r"/res:"+config.PREVIEWPATH)
    def on_button2_pressed(self, widget):
        record()


# starts the web server
def main():
    #start_accesspoint()
    start(MyApp, address='127.0.0.1', port=8081, multiple_instance=False,enable_file_cache=True, update_interval=0.1, start_browser=False)