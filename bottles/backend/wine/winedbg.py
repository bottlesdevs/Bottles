import re
import time
import subprocess

from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.wine.wineserver import WineServer
from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.utils.decorators import cache


class WineDbg(WineProgram):
    program = "Wine debug tool"
    command = "winedbg"
    colors = "debug"

    def __wineserver_status(self):
        return WineServer(self.config).is_alive()

    @cache(seconds=5)
    def get_processes(self):
        """Get all processes running on the wineprefix."""
        processes = []
        parent = None

        if not self.__wineserver_status():
            return processes

        res = self.launch(
            args='--command "info proc"', communicate=True, action_name="get_processes"
        )
        if not res.ready:
            return processes

        lines = res.data.split("\n")
        for w in lines[1:]:  # remove the first line from the output (the header)
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
                    "parent": w_parent,
                }
                processes.append(w)

        return processes

    def wait_for_process(self, name: str, timeout: float = 0.5):
        """Wait for a process to exit."""
        if not self.__wineserver_status():
            return True

        while True:
            processes = self.get_processes()
            if len(processes) == 0:
                break
            if name not in [p["name"] for p in processes]:
                break
            time.sleep(timeout)
        return True

    def kill_process(self, pid: str | None = None, name: str | None = None):
        """
        Kill a process by its PID or name.
        """
        wineboot = WineBoot(self.config)
        if not self.__wineserver_status():
            return

        if pid:
            args = "\n".join(
                ["<< END_OF_INPUTS", f"attach 0x{pid}", "kill", "quit", "END_OF_INPUTS"]
            )
            res = self.launch(args=args, communicate=True, action_name="kill_process")
            if res.has_data and "error 5" in res.data and name:
                subprocess.Popen(
                    f"kill $(pgrep {name[:15]})",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                )
                return
            wineboot.kill()

        if name:
            processes = self.get_processes()
            for p in processes:
                if p["name"] == name:
                    self.kill_process(p["pid"], name)

    def is_process_alive(self, pid: str | None = None, name: str | None = None):
        """
        Check if a process is running on the wineprefix.
        """
        if not self.__wineserver_status():
            return False

        processes = self.get_processes()

        if pid:
            return pid in [p["pid"] for p in processes]
        if name:
            return name in [p["name"] for p in processes]
        return False
