from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.wine.winepath import WinePath

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
        winepath = WinePath(self.config)

        if winepath.is_unix(file):
            # running unix paths with start is not recommended
            # as it can miss important files due to the wrong
            # current working directory
            args = f"/unix /wait {file} {args}"
        else:
            args = f"/wait {file} {args}"

        self.launch(
            args=args,
            comunicate=True,
            terminal=terminal,
            environment=environment,
            cwd=cwd,
            minimal=False,
            action_name="run"
        )
