import os

import logging
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.wineboot import WineBoot


class WineCfg(WineProgram):
    program = "Wine Configuration"
    command = "winecfg"

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
