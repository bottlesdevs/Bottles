import os

from bottles.backend.logger import Logger
from bottles.backend.models.result import Result
from bottles.backend.wine.catalogs import win_versions
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.wineboot import WineBoot

logging = Logger()


class WineCfg(WineProgram):
    program = "Wine Configuration"
    command = "winecfg"

    def get_windows_version(self):
        result = self.launch(
            args="-v", communicate=True, action_name="get_windows_version"
        )
        if not result.ok:
            return result
        version = result.data.strip() if isinstance(result.data, str) else ""
        if version not in win_versions:
            return Result(False, message="Cannot determine the current Windows version.")
        result.data = version
        return result

    def set_windows_version(self, version):
        logging.info(f"Setting Windows version to {version}")

        winedbg = WineDbg(self.config)
        wineboot = WineBoot(self.config)

        wineboot.kill()

        res = self.launch(
            args=f"-v {version}",
            communicate=True,
            environment={
                "DISPLAY": os.environ.get("DISPLAY", ":0"),
                "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", ""),
            },
            action_name="set_windows_version",
        )

        winedbg.wait_for_process("winecfg")
        wineboot.restart()

        return res
