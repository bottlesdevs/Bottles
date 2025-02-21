import re
from functools import lru_cache

from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.utils.manager import ManagerUtils


class WinePath(WineProgram):
    program = "Wine path converter"
    command = "winepath"

    @staticmethod
    @lru_cache
    def is_windows(path: str):
        return ":" in path or "\\" in path

    @staticmethod
    @lru_cache
    def is_unix(path: str):
        return not WinePath.is_windows(path)

    @staticmethod
    @lru_cache
    def __clean_path(path):
        return path.replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()

    @lru_cache
    def to_unix(self, path: str, native: bool = False):
        if native:
            bottle_path = ManagerUtils.get_bottle_path(self.config)
            path = path.replace("\\", "/")
            path = path.replace(
                path[0:2], f"{bottle_path}/dosdevices/{path[0:2].lower()}"
            )
            return self.__clean_path(path)
        args = f"--unix '{path}'"
        res = self.launch(args=args, communicate=True, action_name="--unix")
        return self.__clean_path(res.data)

    @lru_cache
    def to_windows(self, path: str, native: bool = False):
        if native:
            bottle_path = ManagerUtils.get_bottle_path(self.config)
            if "/drive_" in path:
                drive = re.search(r"drive_([a-z])/", path.lower()).group(1)
                path = path.replace(
                    f"{bottle_path}/drive_{drive.lower()}", f"{drive.upper()}:"
                )
            elif "/dosdevices" in path:
                drive = re.search(r"dosdevices/([a-z]):", path.lower()).group(1)
                path = path.replace(
                    f"{bottle_path}/dosdevices/{drive.lower()}", f"{drive.upper()}:"
                )
            path = path.replace("/", "\\")
            return self.__clean_path(path)

        args = f"--windows '{path}'"
        res = self.launch(args=args, communicate=True, action_name="--windows")
        return self.__clean_path(res.data)

    @lru_cache
    def to_long(self, path: str):
        args = f"--long '{path}'"
        res = self.launch(args=args, communicate=True, action_name="--long")
        return self.__clean_path(res.data)

    @lru_cache
    def to_short(self, path: str):
        args = f"--short '{path}'"
        res = self.launch(args=args, communicate=True, action_name="--short")
        return self.__clean_path(res.data)
