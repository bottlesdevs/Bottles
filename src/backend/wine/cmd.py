from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class CMD(WineProgram):
    program = "Wine Command Line"
    command = "cmd"

    def run_batch(
            self,
            batch: str,
            terminal: bool = True,
            args: str = "",
            environment: dict = None,
            cwd: str = None
    ):
        args = f"< {batch} {args}"

        self.launch(
            args=args,
            comunicate=True,
            terminal=terminal,
            environment=environment,
            cwd=cwd,
            action_name="run_batch"
        )
