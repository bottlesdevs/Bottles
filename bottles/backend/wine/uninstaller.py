from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Uninstaller(WineProgram):
    program = "Wine Uninstaller"
    command = "uninstaller"

    def get_uuid(self, name: str = None):
        args = " --list"

        if name is not None:
            args = f"--list | grep -i '{name}' | cut -f1 -d\\|"

        return self.launch(args=args, communicate=True, action_name="get_uuid")

    def from_uuid(self, uuid: str = None):
        args = ""

        if uuid not in [None, ""]:
            args = f"--remove {uuid}"

        return self.launch(args=args, action_name="from_uuid")

    def from_name(self, name: str):
        uuid = self.get_uuid(name)
        uuid = uuid.strip()
        for _uuid in uuid.splitlines():
            self.from_uuid(_uuid)
