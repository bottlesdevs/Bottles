import os

import logging
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.wine.wineserver import WineServer


class WineBridge(WineProgram):
    program = "Wine Bridge"
    command = "WineBridge.exe"
    is_internal = True
    internal_path = "winebridge"

    def __wineserver_status(self):
        return WineServer(self.config).is_alive()

    def is_available(self):
        if os.path.isfile(self.get_command()):
            logging.info(f"{self.program} is available.")
            return True
        return False

    def get_procs(self):
        args = "getProcs"
        processes = []

        if not self.__wineserver_status:
            return processes

        res = self.launch(args=args, communicate=True, action_name="get_procs")
        if not res.ready:
            return processes

        lines = res.data.split("\n")
        for r in lines:
            if r in ["", "\r"]:
                continue

            r = r.split("|")

            if len(r) < 3:
                continue

            processes.append(
                {
                    "pid": r[1],
                    "threads": r[2],
                    "name": r[0],
                    # "parent": r[3]
                }
            )

        return processes

    def kill_proc(self, pid: str):
        args = f"killProc {pid}"
        return self.launch(args=args, communicate=True, action_name="kill_proc")

    def kill_proc_by_name(self, name: str):
        args = f"killProcByName {name}"
        return self.launch(args=args, communicate=True, action_name="kill_proc_by_name")

    def run_exe(self, exec_path: str):
        args = f"runExe {exec_path}"
        return self.launch(args=args, communicate=True, action_name="run_exe")
