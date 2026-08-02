from typing import Optional

from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Explorer(WineProgram):
    program = "Wine Explorer"
    command = "explorer"

    def launch_desktop(
        self,
        desktop: str = "shell",
        width: int = 0,
        height: int = 0,
        program: Optional[str] = None,
        args: Optional[str] = None,
        environment: Optional[dict] = None,
        cwd: Optional[str] = None,
        background: bool = False,
        sandbox_override: Optional[str] = None,
    ):
        _args = f"/desktop={desktop}"

        if width and height:
            _args += f",{width}x{height}"
        if program:
            if background:
                _args += f" start /b /wait {program}"
            else:
                _args += f" {program}"
        if args:
            _args += f" {args}"

        return self.launch(
            args=_args,
            communicate=True,
            action_name="launch_desktop",
            environment=environment,
            cwd=cwd,
            sandbox_override=sandbox_override,
        )
