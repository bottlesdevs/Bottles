from typing import NewType

from bottles.utils import UtilsLogger # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class Start(WineProgram):
    program = "WINE Starter"
    command = "start"

    def run(
        self, 
        file: str, 
        terminal: bool = True, 
        args: str = "",
        environment: dict = {},
        cwd: str = None
    ):
        args = f"{file} {args}"
        
        self.launch(
            args=args,
            comunicate=True,
            terminal=terminal,
            environment=environment,
            cwd=cwd
        )
