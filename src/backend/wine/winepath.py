from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class WinePath(WineProgram):
    program = "WINE path converter"
    command = "winepath"

    @staticmethod
    def is_windows(path: str):
        return ":" in path or "\\" in path

    @staticmethod
    def is_unix(path: str):
        return not WinePath.is_windows(path)

    @staticmethod
    def __clean_path(path):
        return path.replace("\n", " ").replace("\r", " ").replace("\t", " ")

    def to_unix(self, path: str):
        args = f"--unix '{path}'"
        res = self.launch(args=args, comunicate=True, action_name="--unix")
        return self.__clean_path(res)

    def to_windows(self, path: str):
        args = f"--windows '{path}'"
        res = self.launch(args=args, comunicate=True, action_name="--windows")
        return self.__clean_path(res)

    def to_long(self, path: str):
        args = f"--long '{path}'"
        res = self.launch(args=args, comunicate=True, action_name="--long")
        return self.__clean_path(res)

    def to_short(self, path: str):
        args = f"--short '{path}'"
        res = self.launch(args=args, comunicate=True, action_name="--short")
        return self.__clean_path(res)
