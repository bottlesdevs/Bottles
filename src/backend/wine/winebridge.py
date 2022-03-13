import os
from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.wine.wineserver import WineServer

logging = Logger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class WineBridge(WineProgram):
    program = "WINE Bridge"
    command = "WineBridge.exe"
    is_internal = True

    def __wineserver_status(self):
        return WineServer(self.config).is_alive()

    def is_available(self):
        if os.path.isfile(self.get_command()):
            logging.info(f"{self.program} is available.", )
            return True
        return False

    def get_procs(self):
        args = "getProcs"
        processes = []

        if not self.__wineserver_status:
            return processes

        res = self.launch(
            args=args, 
            comunicate=True, 
            action_name="get_procs"
        )
        if res in [None, ""]:
            return processes

        res = res.split("\n")
        for r in res:
            if r in [None, "", "\r"]:
                continue

            r = r.split("|")

            processes.append({
                "pid": r[1],
                "threads": "0",
                "name": r[0],
                "parent": "0"
            })

        return processes

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
