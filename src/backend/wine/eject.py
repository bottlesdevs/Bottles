from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Eject(WineProgram):
    program = "Wine Eject CLI"
    command = "eject"

    def cdrom(self, drive: str, unmount_only: bool = False) -> None:
        args = drive
        if unmount_only:
            args += " -u"
        return self.launch(args=args, comunicate=True, action_name="cdrom")

    def all(self) -> None:
        args = "-a"
        return self.launch(args=args, comunicate=True, action_name="all")
