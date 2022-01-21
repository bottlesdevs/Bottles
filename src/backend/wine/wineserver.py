import os
import time
import subprocess
from typing import NewType

from bottles.utils import UtilsLogger # pyright: reportMissingImports=false
from bottles.backend.manager_utils import ManagerUtils
from bottles.backend.wine.wineprogram import WineProgram

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


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
        time.sleep(1)
        if res.poll() is None:
            return True
        return False
