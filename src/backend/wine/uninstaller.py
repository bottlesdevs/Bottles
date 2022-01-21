from typing import NewType

from bottles.utils import UtilsLogger # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class Uninstaller(WineProgram):
    program = "WINE Uninstaller"
    command = "uninstaller"

    def get_uuid(self, name: str = None):
        args = " --list"

        if name is not None:
            args = f"--list | grep -i '{name}' | cut -f1 -d\|"
        
        return self.launch(args=args, comunicate=True)

    def from_uuid(self, uuid: str = None):
        args = ""

        if uuid not in [None, ""]:
            args = f"--remove {uuid}"
        
        return self.launch(args=args)
    
    def from_name(self, name: str):
        uuid = self.get_uuid(name)
        uuid = uuid.strip()
        for _uuid in uuid.splitlines():
            self.from_uuid(_uuid)
