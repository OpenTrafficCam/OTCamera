import config
from hardware import camera
import remi.gui as gui
from remi import start, App
from time import sleep
from helpers.rpi import start_accesspoint

class MyApp(App):
    def __init__(self, *args):
        super(MyApp, self).__init__(*args)

    def main(self):
        container = gui.VBox(width=800, height=700)
        self.bt = gui.Button('preview')
        self.image = gui.Image(r"/res:"+config.PREVIEWPATH)

        # setting the listener for the onclick event of the button
        self.bt.onclick.do(self.on_button_pressed)

        # appending a widget to another, the first argument is a string key
        container.append(self.image)
        container.append(self.bt)

        # returning the root widget
        return container

    # listener function
    def on_button_pressed(self, widget):
        camera.preview(now=True)
        #container.append(self.image)
        #self.image.set_image(r"/res:/home/pi/cam_test.jpg")
        self.image.set_image(r"/res:"+config.PREVIEWPATH)



# starts the web server
def main():
    start_accesspoint()
    start(MyApp)