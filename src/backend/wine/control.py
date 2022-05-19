from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Control(WineProgram):
    program = "Wine Control Panel"
    command = "control"

    def load_applet(self, name: str):
        args = name
        return self.launch(args=args, comunicate=True, action_name="load_applet")

    def load_joystick(self):
        return self.load_applet("joy.cpl")

    def load_appwiz(self):
        return self.load_applet("appwiz.cpl")

    def load_inetcpl(self):
        return self.load_applet("inetcpl.cpl")
