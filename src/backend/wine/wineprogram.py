from typing import NewType

from bottles.utils import UtilsLogger # pyright: reportMissingImports=false
from bottles.backend.wine.winecommand import WineCommand

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class WineProgram:
    program: str = "unknown"
    command: str = ""
    config: dict = {}
    colors: str = "default"

    def __init__(self, config: BottleConfig):
        self.config = config

    def __get_command(self, args: str = None):
        command = self.command
        if args is not None:
            command += f" {args}"
            
        return command

    def launch(
        self, 
        args: str = None,
        terminal: bool = False, 
        minimal: bool = True,
        comunicate: bool = False,
        environment: dict = {}
    ):
        logging.info(f"Using {self.program}")
        command = self.__get_command(args)
        res = WineCommand(
            self.config,
            command=command,
            terminal=terminal,
            minimal=minimal,
            comunicate=comunicate,
            colors=self.colors,
            environment=environment
        ).run()
        return res

    def launch_terminal(self, args: str = None):
        self.launch(args=args, terminal=True)
    
    def launch_minimal(self, args: str = None):
        self.launch(args=args, minimal=True)
    