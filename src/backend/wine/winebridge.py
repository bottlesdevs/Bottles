import os
from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class WineBridge(WineProgram):
    program = "WINE Bridge"
    command = "WineBridge.exe"
    is_internal = True

    def is_available(self):
        if os.path.isfile(self.get_command()):
            logging.info(f"{self.program} is available.")
            return True

        return False

    def get_procs(self):
        args = "getProcs"
        return self.launch(
            args=args, 
            comunicate=True, 
            action_name="get_procs"
        )

    def kill_proc(self, pid: str):
        args = f"killProc {pid}"
        return self.launch(
            args=args,
            comunicate=True, 
            action_name="kill_proc"
        )

    def kill_proc_by_name(self, name: str):
        args = f"killProcByName {name}"
        return self.launch(
            args=args, 
            comunicate=True, 
            action_name="kill_proc_by_name"
        )

    def run_exe(self, exec_path: str):
        args = f"runExe {exec_path}"
        return self.launch(
            args=args, 
            comunicate=True, 
            action_name="run_exe"
        )
