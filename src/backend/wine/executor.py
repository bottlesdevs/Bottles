import os
import shlex
from typing import NewType

from bottles.backend.logger import Logger # pyright: reportMissingImports=false
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.winecommand import WineCommand
from bottles.backend.wine.cmd import CMD
from bottles.backend.wine.msiexec import MsiExec
from bottles.backend.wine.start import Start
from bottles.backend.wine.winebridge import WineBridge

logging = Logger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class WineExecutor:
    
    def __init__(
        self,
        config: BottleConfig,
        exec_path: str,
        args: str = "",
        terminal: bool = False,
        cwd: str = None,
        environment: dict = False,
        move_file: bool = False,
        move_upd_fn: callable = None,
        post_script: str = None
    ):
        logging.info("Launching an executable…")
        self.config = config
        self.__validate_path(exec_path)

        if move_file:
            exec_path = self.__move_file(exec_path, move_upd_fn)
        
        self.exec_type = self.__get_exec_type(exec_path)
        self.exec_path = shlex.quote(exec_path)
        self.args = args
        self.terminal = terminal
        self.cwd = cwd
        self.environment = environment
        self.post_script = post_script

    def __validate_path(self, exec_path):
        if exec_path in [None, ""]:
            logging.error("No executable file path provided.")
            return False
        
        if ":\\" in exec_path:
            logging.warning("Windows path detected. Avoiding validation.")
            return True
        
        if not os.path.isfile(exec_path):
            _msg = f"Executable file path does not exist: {exec_path}"
            if "FLATPAK_ID" in os.environ:
                _msg = f"Executable file path does not exist or is not accessible by the Flatpak: {exec_path}"
            logging.error(_msg)
            return False

    def __move_file(self, exec_path, move_upd_fn):
        new_path = ManagerUtils.move_file_to_bottle(
            file_path=exec_path,
            config=self.config,
            fn_update=move_upd_fn
        )
        if new_path:
            exec_path = new_path
        
        self.__validate_path(exec_path)
        
        return exec_path
    
    def __get_exec_type(self, exec_path):
        if exec_path.endswith(".exe"):
            return "exe"
        elif exec_path.endswith(".msi"):
            return "msi"
        elif exec_path.endswith(".bat"):
            return "batch"
        elif exec_path.endswith(".lnk"):
            return "lnk"
        elif exec_path.endswith(".dll"):
            return "dll"
        else:
            logging.error(f"Unsupported executable type: {exec_path}")
            return False
    
    def run(self):
        if self.exec_type in ["exe"]:
            return self.__launch_with_bridge()
        elif self.exec_type == "msi":
            return self.__launch_exe()
        elif self.exec_type == "batch":
            return self.__launch_batch()
        elif self.exec_type == "lnk":
            return self.__launch_lnk()
        elif self.exec_type == "dll":
            return self.__launch_dll()
        else:
            return False
    
    def __launch_with_bridge(self):
        winebridge = WineBridge(self.config)

        if winebridge.is_available():
            res = winebridge.run_exe(self.exec_path)
            return Result(
                status=True,
                data={"output": res}
            )
        else:
            if self.exec_type == "exe":
                return self.__launch_exe()
            elif self.exec_type == "msi":
                return self.__launch_msi()
            else:
                return False

    def __launch_exe(self):
        winebridge = WineBridge(self.config)
        if winebridge.is_available():
            res = winebridge.run_exe(self.exec_path)
            return Result(
                status=True,
                data={"output": res}
            )

        winecmd = WineCommand(
            self.config,
            command=self.exec_path,
            arguments=self.args,
            terminal=self.terminal,
            cwd=self.cwd,
            environment=self.environment,
            comunicate=True,
            post_script=self.post_script
        )
        res = winecmd.run()
        return Result(
            status=True,
            data={"output": res}
        )
    
    def __launch_msi(self):
        msiexec = MsiExec(self.config)
        res = msiexec.install(
            pkg_path=self.exec_path,
            args=self.args,
            terminal=self.terminal,
            cwd=self.cwd,
            environment=self.environment
        )
        return Result(
            status=True,
            data={"output": res}
        )
    
    def __launch_batch(self):
        cmd = CMD(self.config)
        res = cmd.run_batch(
            batch=self.exec_path,
            terminal=self.terminal,
            args=self.args,
            environment=self.environment,
            cwd=self.cwd
        )
        return Result(
            status=True,
            data={"output": res}
        )
    
    def __launch_lnk(self):
        start = Start(self.config)
        res = start.run(
            file=self.exec_path,
            terminal=self.terminal,
            args=self.args,
            environment=self.environment,
            cwd=self.cwd
        )
        return Result(
            status=True,
            data={"output": res}
        )

    def __launch_dll(self):
        logging.warning("DLLs are not supported yet.")
        return Result(
            status=False, 
            data={"error": "DLLs are not supported yet."}
        )
