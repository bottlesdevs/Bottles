import os

import logging
from bottles.backend.globals import Paths
from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.winecommand import WineCommand


class WineProgram:
    program: str = "unknown"
    command: str = ""
    config: BottleConfig
    colors: str = "default"
    is_internal: bool = False
    internal_path: str = ""

    def __init__(self, config: BottleConfig, silent=False):
        if not isinstance(config, BottleConfig):
            raise TypeError(
                "config should be BottleConfig type, but it was %s" % type(config)
            )
        self.config = config
        self.silent = silent

    def get_command(self, args: str | None = None):
        command = self.command

        if self.is_internal:
            command = os.path.join(Paths.base, self.internal_path, command)

        if args is not None:
            command += f" {args}"

        return command

    def launch(
        self,
        args: tuple | str | None = None,
        terminal: bool = False,
        minimal: bool = True,
        communicate: bool = False,
        environment: dict | None = None,
        pre_script: str | None = None,
        post_script: str | None = None,
        cwd: str | None = None,
        midi_soundfont: str | None = None,
        action_name: str = "launch",
    ):
        if environment is None:
            environment = {}

        if not self.silent:
            logging.info(f"Using {self.program} -- {action_name}")

        if isinstance(args, tuple):
            wineprogram_args = args[0]
            program_args = args[1]
        else:
            wineprogram_args = args
            program_args = None

        command = self.get_command(wineprogram_args)
        res = WineCommand(
            self.config,
            command=command,
            terminal=terminal,
            minimal=minimal,
            communicate=communicate,
            colors=self.colors,
            environment=environment,
            pre_script=pre_script,
            post_script=post_script,
            cwd=cwd,
            midi_soundfont=midi_soundfont,
            arguments=program_args,
        )

        # logging.info("Executing command:", res.command)
        res = res.run()
        return res

    def launch_terminal(self, args: str | None = None):
        self.launch(args=args, terminal=True, action_name="launch_terminal")

    def launch_minimal(self, args: str | None = None):
        self.launch(args=args, minimal=True, action_name="launch_minimal")
