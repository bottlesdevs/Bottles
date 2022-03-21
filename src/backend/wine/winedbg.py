import re
import time
import subprocess
from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.wine.wineserver import WineServer
from bottles.backend.wine.wineboot import WineBoot

logging = Logger()


class WineDbg(WineProgram):
    program = "WINE debug tool"
    command = "winedbg"
    colors = "debug"

    def __wineserver_status(self):
        return WineServer(self.config).is_alive()

    def get_processes(self):
        """Get all processes running on the wineprefix."""
        processes = []
        parent = None

        if not self.__wineserver_status:
            return processes

        res = self.launch(
            args='--command "info proc"',
            comunicate=True,
            action_name="get_processes"
        )
        if res in [None, ""]:
            return processes

        res = res.split("\n")

        # remove the first line from the output (the header)
        del res[0]

        for w in res:
            w = re.sub("\\s{2,}", " ", w)[1:].replace("'", "")

            if "\\_" in w:
                w = w.replace("\\_ ", "")
                w += " child"

            w = w.split(" ")
            w_parent = None

            if len(w) >= 3 and w[1].isdigit():
                w_pid = w[0]
                w_threads = w[1]
                w_name = w[2]

                if len(w) == 3:
                    parent = w_pid
                else:
                    w_parent = parent

                w = {
                    "pid": w_pid,
                    "threads": w_threads,
                    "name": w_name,
                    "parent": w_parent
                }
                processes.append(w)

        return processes

    def wait_for_process(self, name: str, timeout: int = .5):
        """Wait for a process to exit."""
        wineserver = WineServer(self.config)
        if not wineserver.is_alive():
            return True

        while True:
            processes = self.get_processes()
            if len(processes) == 0:
                break
            if name not in [p["name"] for p in processes]:
                break
            time.sleep(timeout)
        return True

    def kill_process(self, pid: str = None, name: str = None):
        '''
        Kill a process by its PID or name.
        '''
        wineserver = WineServer(self.config)
        wineboot = WineBoot(self.config)
        if not wineserver.is_alive():
            return

        if pid:
            args = "\n".join([
                "<< END_OF_INPUTS",
                f"attach 0x{pid}",
                "kill",
                "quit",
                "END_OF_INPUTS"
            ])
            res = self.launch(
                args=args,
                comunicate=True,
                action_name="kill_process"
            )
            if "error 5" in res and name:
                res = subprocess.Popen(
                    f"kill $(pgrep {name[:15]})",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True
                )
                return res
            return wineboot.kill()

        if name:
            processes = self.get_processes()
            for p in processes:
                if p["name"] == name:
                    self.kill_process(p["pid"], name)

    def is_process_alive(self, pid: str = None, name: str = None):
        '''
        Check if a process is running on the wineprefix.
        '''
        if not self.__wineserver_status:
            return False

        processes = self.get_processes()

        if pid:
            return pid in [p["pid"] for p in processes]
        if name:
            return name in [p["name"] for p in processes]
        return False
