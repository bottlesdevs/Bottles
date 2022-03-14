from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class WinePath(WineProgram):
    program = "WINE path converter"
    command = "winepath"

    @staticmethod
    def is_windows(path: str):
        return ":" in path or "\\" in path

    @staticmethod
    def is_unix(path: str):
        return not WinePath.is_windows(path)

    def to_unix(self, path: str):
        args = f"--unix {path}"

        return self.launch(args=args, comunicate=True, action_name="--unix")

    def to_windows(self, path: str):
        args = f"--windows {path}"

        return self.launch(args=args, comunicate=True, action_name="--windows")

    def to_long(self, path: str):
        args = f"--long {path}"

        return self.launch(args=args, comunicate=True, action_name="--long")

    def to_short(self, path: str):
        args = f"--short {path}"

        return self.launch(args=args, comunicate=True, action_name="--short")
