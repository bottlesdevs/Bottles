import os
from typing import NewType

from bottles.utils import UtilsLogger # pyright: reportMissingImports=false
from bottles.backend.globals import Paths
from bottles.backend.manager_utils import ManagerUtils
from bottles.backend.wine.wineprogram import WineProgram

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class WineBridge(WineProgram):
    program = "WINE Bridge"
    command = f"{Paths.base}/WineBridge.exe"

    def is_available(self):
        if os.path.isfile(self.command):
            logging.info(f"{self.program} is available.")
            return True

        return False

    def get_procs(self):
        args = "getProcs"
        return self.launch(args=args, comunicate=True)

    def kill_proc(self, pid: str):
        args = f"killProc {pid}"
        return self.launch(args=args, comunicate=True)

    def kill_proc_by_name(self, name: str):
        args = f"killProcByName {name}"
        return self.launch(args=args, comunicate=True)

    def run_exe(self, exec_path: str):
        args = f"runExe {exec_path}"
        return self.launch(args=args, comunicate=True)
