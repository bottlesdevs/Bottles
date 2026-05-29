from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram
from bottles.backend.wine.wineserver import WineServer

import os
import signal

logging = Logger()


class WineBoot(WineProgram):
    program = "Wine Runtime tool"
    command = "wineboot"

    def send_status(self, status: int):
        if status == -2:
            return self.nv_stop_all_processes()

        states = {-1: "force", 0: "-k", 1: "-r", 2: "-s", 3: "-u", 4: "-i"}
        envs = {
            "WINEDEBUG": "-all",
            "DISPLAY": ":3.0",
            "WINEDLLOVERRIDES": "winemenubuilder=d",
        }

        # Under a dedicated sandbox the wine processes live in a separate
        # flatpak-spawn instance, so wineboot/wineserver cannot reach them.
        # Kill the tracked sandbox launchers directly when stopping.
        if status in (-1, 0) and self.config.Parameters.sandbox:
            self.__terminate_sandbox()

        if status == 0 and not WineServer(self.config).is_alive():
            logging.info("There is no running wineserver.")
            return

        if status in states:
            args = f"{states[status]} /nogui"
            self.launch(
                args=args,
                environment=envs,
                communicate=True,
                action_name=f"send_status({states[status]})",
            )
        else:
            raise ValueError(f"[{status}] is not a valid status for wineboot!")

    def force(self):
        return self.send_status(-1)

    def kill(self, force_if_stalled: bool = False):
        self.send_status(0)

        if force_if_stalled:
            wineserver = WineServer(self.config)
            if wineserver.is_alive():
                wineserver.force_kill()
                wineserver.wait()

    def restart(self):
        return self.send_status(1)

    def shutdown(self):
        return self.send_status(2)

    def update(self):
        return self.send_status(3)

    def init(self):
        return self.send_status(4)

    def __terminate_sandbox(self):
        from bottles.backend.managers.sandbox import SandboxManager
        from bottles.backend.utils.manager import ManagerUtils

        prefix = ManagerUtils.get_bottle_path(self.config)
        killed = SandboxManager.terminate_prefix(prefix)
        if killed:
            logging.info(f"Terminated {killed} sandbox launcher(s) for the bottle.")

    def nv_stop_all_processes(self):
        if self.config.Parameters.sandbox:
            self.__terminate_sandbox()
        try:
            for pid in os.listdir("/proc"):
                if pid.isdigit():
                    try:
                        with open(f"/proc/{pid}/environ", "r") as env_file:
                            env_vars = env_file.read()
                            if f"BOTTLE={self.config.Path}" in env_vars:
                                os.kill(int(pid), signal.SIGTERM)
                                logging.info(f"Killed process with PID {pid}.")
                    except (FileNotFoundError, ProcessLookupError):
                        continue
        except Exception as e:
            logging.error(f"Error stopping processes: {e}")
