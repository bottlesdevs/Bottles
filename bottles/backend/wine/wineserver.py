import os
import subprocess
import time

from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.proc import ProcUtils
from bottles.backend.wine.wineprogram import WineProgram


class WineServer(WineProgram):
    program = "Wine Server"
    command = "wineserver"

    def is_alive(self):
        config = self.config

        # If the config has no Runner, skip the execution
        if not config.Runner:
            return False

        # Perform native check before wasting time using wine
        res = subprocess.Popen(["pgrep", "wineserver"], stdout=subprocess.PIPE)
        if res.stdout.read() == b"":
            return False

        # Check using wine
        bottle = ManagerUtils.get_bottle_path(config)
        runner = ManagerUtils.get_runner_path(config.Runner)

        env = os.environ.copy()
        env["WINEPREFIX"] = bottle
        env["PATH"] = f"{runner}/bin:{env['PATH']}"
        res = subprocess.Popen(
            "wineserver -w",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            cwd=bottle,
            env=env,
        )
        time.sleep(0.5)
        if res.poll() is None:
            res.kill()  # kill the process to avoid zombie incursion
            return True
        return False

    def wait(self):
        config = self.config
        bottle = ManagerUtils.get_bottle_path(config)
        runner = ManagerUtils.get_runner_path(config.Runner)

        env = os.environ.copy()
        env["WINEPREFIX"] = bottle
        env["PATH"] = f"{runner}/bin:{env['PATH']}"

        subprocess.Popen(
            "wineserver -w",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            cwd=bottle,
            env=env,
        ).wait()

    def kill(self, signal: int = -1):
        args = "-k"
        if signal != -1:
            args += str(signal)

        self.launch(
            args=args, communicate=True, action_name="sending signal to the wine server"
        )

    def force_kill(self):
        bottle = ManagerUtils.get_bottle_path(self.config)
        procs = ProcUtils.get_by_env(f"WINEPREFIX={bottle}")
        for proc in procs:
            proc.kill()

        if len(procs) == 0:
            self.kill(9)
