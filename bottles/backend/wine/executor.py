import os
import shlex
import uuid
from typing import NewType, Union

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.winecommand import WineCommand
from bottles.backend.wine.cmd import CMD
from bottles.backend.wine.msiexec import MsiExec
from bottles.backend.wine.start import Start
from bottles.backend.wine.explorer import Explorer
from bottles.backend.wine.winepath import WinePath
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.winebridge import WineBridge

logging = Logger()


class WineExecutor:

    def __init__(
            self,
            config: dict,
            exec_path: str,
            args: str = "",
            terminal: bool = False,
            cwd: str = None,
            environment: dict = None,
            move_file: bool = False,
            move_upd_fn: callable = None,
            post_script: str = None,
            monitoring: list = None,
            override_dxvk: bool = None,
            override_vkd3d: bool = None,
            override_nvapi: bool = None,
            override_fsr: bool = None,
            override_pulse_latency: bool = None,
            override_virt_desktop: bool = None
    ):
        logging.info("Launching an executable…")
        self.config = config
        self.__validate_path(exec_path)

        if monitoring is None:
            monitoring = []

        if environment is None:
            environment = {}

        if move_file:
            exec_path = self.__move_file(exec_path, move_upd_fn)

        self.exec_type = self.__get_exec_type(exec_path)
        self.exec_path = shlex.quote(exec_path)
        self.args = args
        self.terminal = terminal
        self.cwd = self.__get_cwd(cwd)
        self.environment = environment
        self.post_script = post_script
        self.monitoring = monitoring
        self.use_virt_desktop = override_virt_desktop

        env_dll_overrides = []
        if override_dxvk is not None \
            and not override_dxvk \
            and self.config["Parameters"]["dxvk"]:
                env_dll_overrides.append("d3d9,d3d11,d3d10core,dxgi=b")

        if override_vkd3d is not None \
            and not override_vkd3d \
            and self.config["Parameters"]["vkd3d"]:
                env_dll_overrides.append("d3d12=b")

        if override_nvapi is not None \
            and not override_nvapi \
            and self.config["Parameters"]["dxvk_nvapi"]:
                env_dll_overrides.append("nvapi,nvapi64=b")

        if override_fsr is not None and override_fsr:
            self.environment["WINE_FULLSCREEN_FSR"] = "1"
            self.environment["WINE_FULLSCREEN_FSR_STRENGTH"] = str(self.config['Parameters']['fsr_level'])

        if override_pulse_latency is not None and override_pulse_latency:
            self.environment["PULSE_LATENCY_MSEC"] = "60"

        if "WINEDLLOVERRIDES" in self.environment:
            self.environment["WINEDLLOVERRIDES"] += "," + ",".join(env_dll_overrides)
        else:
            self.environment["WINEDLLOVERRIDES"] = ",".join(env_dll_overrides)

    @classmethod
    def run_program(cls,config: dict, program: dict, terminal: bool=False):
        if program is None:
            logging.warning("The program entry is not well formatted.")
            
        dxvk = config["Parameters"]["dxvk"]
        vkd3d = config["Parameters"]["vkd3d"]
        nvapi = config["Parameters"]["dxvk_nvapi"]
        fsr = config["Parameters"]["fsr"]
        pulse_latency = config["Parameters"]["pulseaudio_latency"]
        virt_desktop = config["Parameters"]["virtual_desktop"]

        if program.get("dxvk") != dxvk:
            dxvk = program.get("dxvk")
        if program.get("vkd3d") != vkd3d:
            vkd3d = program.get("vkd3d")
        if program.get("dxvk_nvapi") != nvapi:
            nvapi = program.get("dxvk_nvapi")
        if program.get("fsr") != fsr:
            fsr = program.get("fsr")
        if program.get("pulseaudio_latency") != pulse_latency:
            pulse_latency = program.get("pulseaudio_latency")
        if program.get("virtual_desktop") != virt_desktop:
            virt_desktop = program.get("virtual_desktop")

        return cls(
            config=config,
            exec_path=program["path"],
            args=program["arguments"],
            cwd=program["folder"],
            post_script=program.get("script", None),
            terminal=terminal,
            override_dxvk=dxvk,
            override_vkd3d=vkd3d,
            override_nvapi=nvapi,
            override_fsr=fsr,
            override_pulse_latency=pulse_latency,
            override_virt_desktop=virt_desktop
        ).run()

    def __get_cwd(self, cwd: str) -> Union[str, None]:
        winepath = WinePath(self.config)
        if cwd in [None, ""]:
            path = self.exec_path
            if winepath.is_windows(self.exec_path):
                path = "\\".join(path.split("\\")[:-1])
                path = winepath.to_unix(path)
            if path.startswith(("'", '"')):
                path = path[1:]
            if path.endswith(("'", '"')):
                path = path[:-1]
            return os.path.dirname(path)
        return cwd  # will be set by WineCommand if None

    @staticmethod
    def __validate_path(exec_path):
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
            logging.error(_msg, )
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

    @staticmethod
    def __get_exec_type(exec_path):
        _exec = exec_path.lower()
        if _exec.endswith(".exe"):
            return "exe"
        if _exec.endswith(".msi"):
            return "msi"
        if _exec.endswith(".bat"):
            return "batch"
        if _exec.endswith(".lnk"):
            return "lnk"
        if _exec.endswith(".dll"):
            return "dll"

        logging.warning(f"Not a common executable type, trying to launch it anyway.")
        return "unsupported"

    def run_cli(self):
        """
        We need to launch the application and then exit,
        so we use Wine Starter, which will exit as soon
        as the program is launched
        """
        winepath = WinePath(self.config)
        start = Start(self.config)

        if winepath.is_unix(self.exec_path):
            return self.__launch_with_bridge()

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

    def run(self):
        if self.exec_type in ["exe", "msi"]:
            return self.__launch_with_bridge()
        if self.exec_type == "batch":
            return self.__launch_batch()
        if self.exec_type in ["lnk", "unsupported"]:
            return self.__launch_with_starter()
        if self.exec_type == "dll":
            return self.__launch_dll()
        return Result(
            status=False,
            data={"message": "Unknown executable type."}
        )

    def __launch_with_bridge(self):
        # winebridge = WineBridge(self.config)
        # if winebridge.is_available():
        #     res = winebridge.run_exe(self.exec_path)
        #     return Result(
        #         status=True,
        #         data={"output": res}
        #     )
        winepath = WinePath(self.config)
        if self.use_virt_desktop:
            if winepath.is_unix(self.exec_path):
                self.exec_path = winepath.to_windows(self.exec_path)
            return self.__launch_with_explorer()
        if winepath.is_windows(self.exec_path):
            return self.__launch_with_starter()
        if self.exec_type == "exe":
            return self.__launch_exe()
        if self.exec_type == "msi":
            return self.__launch_msi()
        if self.exec_type == "batch":
            return self.__launch_batch()

        logging.error(f'exec_type {self.exec_type} is not valid')
        return Result(
            status=False,
            data={"message": "Unknown executable type."}
        )

    def __launch_exe(self):
        # winebridge = WineBridge(self.config)
        # if winebridge.is_available():
        #     res = winebridge.run_exe(self.exec_path)
        #     return Result(
        #         status=True,
        #         data={"output": res}
        #     )

        winecmd = WineCommand(
            self.config,
            command=self.exec_path,
            arguments=self.args,
            terminal=self.terminal,
            cwd=self.cwd,
            environment=self.environment,
            communicate=True,
            post_script=self.post_script
        )
        res = winecmd.run()
        self.__set_monitors()
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
        self.__set_monitors()
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

    def __launch_with_starter(self):
        start = Start(self.config)
        res = start.run(
            file=self.exec_path,
            terminal=self.terminal,
            args=self.args,
            environment=self.environment,
            cwd=self.cwd
        )
        self.__set_monitors()
        return Result(
            status=True,
            data={"output": res}
        )

    def __launch_with_explorer(self):
        w, h = self.config["Parameters"]["virtual_desktop_res"].split("x")
        start = Explorer(self.config)
        res = start.launch_desktop(
            desktop=str(uuid.uuid4()),
            width=w,
            height=h,
            program=self.exec_path,
            args=self.args,
            environment=self.environment,
            cwd=self.cwd
        )
        self.__set_monitors()
        return Result(
            status=True,
            data={"output": res}
        )

    @staticmethod
    def __launch_dll():
        logging.warning("DLLs are not supported yet.")
        return Result(
            status=False,
            data={"error": "DLLs are not supported yet."}
        )

    def __set_monitors(self):
        if not self.monitoring:
            return

        logging.info("Starting {} monitors".format(len(self.monitoring)))

        winedbg = WineDbg(self.config, silent=True)
        for m in self.monitoring:
            winedbg.wait_for_process(name=m)
