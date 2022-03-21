from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Start(WineProgram):
    program = "WINE Starter"
    command = "start"

    def run(
            self,
            file: str,
            terminal: bool = True,
            args: str = "",
            environment: dict = None,
            cwd: str = None
    ):
        args = f"{file} {args}"

        self.launch(
            args=args,
            comunicate=True,
            terminal=terminal,
            environment=environment,
            cwd=cwd,
            action_name="run"
        )
