import os
from sys import stdout
import time
import subprocess
from typing import NewType

from bottles.backend.utils.manager import ManagerUtils  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.logger import Logger

logging = Logger()


class WineServer(WineProgram):
    program = "WINE Server"
    command = "wineserver"

    def is_alive(self):
        config = self.config

        # TODO: workaround, there is something who make calls without runner
        if not config.get("Runner"):
            return False

        bottle = ManagerUtils.get_bottle_path(config)
        runner = ManagerUtils.get_runner_path(config.get("Runner"))

        if config.get("Environment", "Custom") == "Steam":
            bottle = config.get("Path")
            runner = config.get("RunnerPath")

        env = os.environ.copy()
        env["WINEPREFIX"] = bottle
        env["PATH"] = f"{runner}/bin:{env['PATH']}"
        res = subprocess.Popen(
            "wineserver -w",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            cwd=bottle,
            env=env
        )
        time.sleep(.5)
        if res.poll() is None:
            res.kill()  # kill the process to avoid zombie incursion
            return True
        return False

    def wait(self):
        config = self.config
        bottle = ManagerUtils.get_bottle_path(config)
        runner = ManagerUtils.get_runner_path(config.get("Runner"))

        env = os.environ.copy()
        env["WINEPREFIX"] = bottle
        env["PATH"] = f"{runner}/bin:{env['PATH']}"

        subprocess.Popen(
            "wineserver -w",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            cwd=bottle,
            env=env
        ).wait()
