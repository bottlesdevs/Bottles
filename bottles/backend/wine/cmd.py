from typing import Optional

from bottles.backend.logger import Logger
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
            environment: Optional[dict] = None,
            cwd: Optional[str] = None
    ):
        args = f"/c {batch} {args}"

        self.launch(
            args=args,
            communicate=True,
            terminal=terminal,
            environment=environment,
            cwd=cwd,
            action_name="run_batch"
        )
