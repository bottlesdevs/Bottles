import os
import subprocess

from bottles.backend.logger import Logger
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.proc import ProcUtils
from bottles.backend.utils.steam import SteamUtils
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class WineServer(WineProgram):
    program = "Wine Server"
    command = "wineserver"

    def is_alive(self):
        config = self.config

        # If the config has no Runner, skip the execution
        if not config.Runner:
            return False

        bottle = ManagerUtils.get_bottle_path(config)

        if config.Environment == "Steam":
            bottle = config.Path

        if not os.path.isdir(bottle):
            return False

        try:
            res = self._run(["-w"])
        except FileNotFoundError:
            return False
        try:
            res.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            res.kill()
            res.wait()
            return True
        return False

    def _run(self, args):
        config = self.config
        bottle = ManagerUtils.get_bottle_path(config)
        runner = ManagerUtils.get_runner_path(config.Runner)

        if config.Environment == "Steam":
            bottle = config.Path
            runner = config.RunnerPath

        if SteamUtils.is_proton(runner):
            runner = SteamUtils.get_dist_directory(runner)

        env = os.environ.copy()
        env["WINEPREFIX"] = bottle
        command = "wineserver"
        if not config.Runner.startswith("sys-"):
            command = os.path.join(runner, "bin", "wineserver")
            env["PATH"] = f"{runner}/bin:{env['PATH']}"

        return subprocess.Popen(
            [command, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=bottle,
            env=env,
        )

    def _wait(self, args, timeout=None):
        process = self._run(args)
        try:
            if timeout is None:
                return process.wait()
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise

    def wait(self, timeout=None):
        return self._wait(["-w"], timeout)

    def kill(self, signal: int = -1, timeout=None):
        args = "-k"
        if signal != -1:
            args += str(signal)

        if not self.silent:
            logging.info("Using Wine Server -- sending signal to the wine server")
        self.returncode = self._wait([args], timeout)

    def stop(self, timeout=30):
        if self.config.Parameters.sandbox:
            from bottles.backend.managers.sandbox import SandboxManager

            bottle = ManagerUtils.get_bottle_path(self.config)
            SandboxManager.terminate_prefix(bottle, timeout=timeout)
            return True

        self.kill(timeout=timeout)
        return self.returncode == 0 and self.wait(timeout=timeout) == 0

    def force_kill(self):
        bottle = ManagerUtils.get_bottle_path(self.config)

        # Under a dedicated sandbox the processes are not visible on the host,
        # so kill the tracked sandbox launchers (their process groups) instead.
        if self.config.Parameters.sandbox:
            from bottles.backend.managers.sandbox import SandboxManager

            SandboxManager.terminate_prefix(bottle)
            return

        procs = ProcUtils.get_by_env(f"WINEPREFIX={bottle}")
        for proc in procs:
            proc.kill(9)

        self.kill(9)
