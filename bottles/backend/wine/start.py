import shlex
from typing import Optional

from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.wine.winepath import WinePath

logging = Logger()


class Start(WineProgram):
    program = "Wine Starter"
    command = "start"

    def run(
        self,
        file: str,
        terminal: bool = True,
        args: str = "",
        environment: Optional[dict] = None,
        pre_script: Optional[str] = None,
        post_script: Optional[str] = None,
        pre_script_args: Optional[str] = None,
        post_script_args: Optional[str] = None,
        cwd: Optional[str] = None,
        background: bool = False,
        sandbox_override: Optional[str] = None,
    ):
        winepath = WinePath(self.config)
        start_options = "/b " if background else ""
        working_dir = cwd
        if working_dir not in [None, ""] and winepath.is_unix(working_dir):
            working_dir = winepath.to_windows(
                working_dir,
                sandbox_override=sandbox_override,
            )
        directory_option = (
            f"/d {shlex.quote(working_dir)} " if working_dir else ""
        )

        if winepath.is_unix(file):
            # running unix paths with start is not recommended
            # as it can miss important files due to the wrong
            # current working directory
            _args = f"{start_options}/wait {directory_option}/unix {file}"
        else:
            _args = f"{start_options}/wait {directory_option}{file}"

        self.launch(
            args=(_args, args),
            communicate=True,
            terminal=terminal,
            environment=environment,
            pre_script=pre_script,
            post_script=post_script,
            pre_script_args=pre_script_args,
            post_script_args=post_script_args,
            cwd=cwd,
            minimal=False,
            action_name="run",
            sandbox_override=sandbox_override,
        )
