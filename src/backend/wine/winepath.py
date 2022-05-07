from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


class WinePath(WineProgram):
    program = "Wine path converter"
    command = "winepath"

    @staticmethod
    def is_windows(path: str):
        return ":" in path or "\\" in path

    @staticmethod
    def is_unix(path: str):
        return not WinePath.is_windows(path)

    @staticmethod
    def __clean_path(path):
        return path.replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()

    def to_unix(self, path: str, native: bool = False):
        if native:
            bottle_path = ManagerUtils.get_bottle_path(self.config)
            path = path.replace("\\", "/")
            path = path.replace(
                path[0:2],
                f"{bottle_path}/dosdevices/{path[0:2].lower()}"
            )
            return self.__clean_path(path)
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
