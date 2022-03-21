from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class MsiExec(WineProgram):
    program = "WINE MSI Installer"
    command = "msiexec"

    def install(
            self,
            pkg_path: str,
            args: str = "",
            terminal: bool = False,
            cwd: str = None,
            environment: dict = None
    ):
        args = f"/i {pkg_path} {args}"

        self.launch(
            args=args,
            comunicate=True,
            minimal=True,
            environment=environment,
            terminal=terminal,
            cwd=cwd,
            action_name="install"
        )
