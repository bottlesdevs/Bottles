import os
import shlex
import uuid

from bottles.backend.dlls.dxvk import DXVKComponent
from bottles.backend.dlls.nvapi import NVAPIComponent
from bottles.backend.dlls.vkd3d import VKD3DComponent
import logging
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.cmd import CMD
from bottles.backend.wine.explorer import Explorer
from bottles.backend.wine.msiexec import MsiExec
from bottles.backend.wine.start import Start
from bottles.backend.wine.winecommand import WineCommand
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.winepath import WinePath


class WineExecutor:
    def __init__(
        self,
        config: BottleConfig,
        exec_path: str,
        args: str = "",
        terminal: bool = False,
        environment: dict | None = None,
        move_file: bool = False,
        move_upd_fn: callable = None,
        pre_script: str | None = None,
        post_script: str | None = None,
        cwd: str | None = None,
        midi_soundfont: str | None = None,
        monitoring: list | None = None,
        program_dxvk: bool | None = None,
        program_vkd3d: bool | None = None,
        program_nvapi: bool | None = None,
        program_fsr: bool | None = None,
        program_gamescope: bool | None = None,
        program_virt_desktop: bool | None = None,
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
        self.environment = environment
        self.pre_script = pre_script
        self.post_script = post_script
        self.cwd = self.__get_cwd(cwd)
        self.midi_soundfont = midi_soundfont
        self.monitoring = monitoring
        self.use_gamescope = program_gamescope
        self.use_virt_desktop = program_virt_desktop

        env_dll_overrides = []

        # None = use global DXVK value
        if program_dxvk is not None:
            # DXVK is globally activated, but disabled for the program
            if not program_dxvk and self.config.Parameters.dxvk:
                # Disable DXVK for the program
                override_dxvk = DXVKComponent.get_override_keys() + "=b"
                env_dll_overrides.append(override_dxvk)

        if program_vkd3d is not None:
            if not program_vkd3d and self.config.Parameters.vkd3d:
                override_vkd3d = VKD3DComponent.get_override_keys() + "=b"
                env_dll_overrides.append(override_vkd3d)

        if program_nvapi is not None:
            if not program_nvapi and self.config.Parameters.dxvk_nvapi:
                override_nvapi = NVAPIComponent.get_override_keys() + "=b"
                env_dll_overrides.append(override_nvapi)

        if program_fsr is not None and program_fsr != self.config.Parameters.fsr:
            self.environment["WINE_FULLSCREEN_FSR"] = "1" if program_fsr else "0"
            self.environment["WINE_FULLSCREEN_FSR_STRENGTH"] = str(
                self.config.Parameters.fsr_sharpening_strength
            )
            if self.config.Parameters.fsr_quality_mode:
                self.environment["WINE_FULLSCREEN_FSR_MODE"] = str(
                    self.config.Parameters.fsr_quality_mode
                )

        if (
            program_gamescope is not None
            and program_gamescope != self.config.Parameters.gamescope
        ):
            self.environment["GAMESCOPE"] = "1" if program_gamescope else "0"

        if env_dll_overrides:
            if "WINEDLLOVERRIDES" in self.environment:
                self.environment["WINEDLLOVERRIDES"] += ";" + ";".join(
                    env_dll_overrides
                )
            else:
                self.environment["WINEDLLOVERRIDES"] = ";".join(env_dll_overrides)

    @classmethod
    def run_program(cls, config: BottleConfig, program: dict, terminal: bool = False):
        if program is None:
            logging.warning("The program entry is not well formatted.")

        return cls(
            config=config,
            exec_path=program.get("path"),
            args=program.get("arguments"),
            pre_script=program.get("pre_script"),
            post_script=program.get("post_script"),
            cwd=program.get("folder"),
            midi_soundfont=program.get("midi_soundfont"),
            terminal=terminal,
            program_dxvk=program.get("dxvk"),
            program_vkd3d=program.get("vkd3d"),
            program_nvapi=program.get("dxvk_nvapi"),
            program_fsr=program.get("fsr"),
            program_gamescope=program.get("gamescope"),
            program_virt_desktop=program.get("virtual_desktop"),
        ).run()

    def __get_cwd(self, cwd: str) -> str | None:
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
            logging.error(
                _msg,
            )
            return False

    def __move_file(self, exec_path, move_upd_fn):
        new_path = ManagerUtils.move_file_to_bottle(
            file_path=exec_path, config=self.config, fn_update=move_upd_fn
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

        logging.warning("Not a common executable type, trying to launch it anyway.")
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
            pre_script=self.pre_script,
            post_script=self.post_script,
            cwd=self.cwd,
            midi_soundfont=self.midi_soundfont,
        )
        return Result(status=True, data={"output": res})

    def run(self) -> Result:
        match self.exec_type:
            case "exe" | "msi":
                return self.__launch_with_bridge()
            case "batch":
                return self.__launch_batch()
            case "lnk" | "unsupported":
                return self.__launch_with_starter()
            case "dll":
                return self.__launch_dll()
            case _:
                return Result(
                    status=False, data={"message": "Unknown executable type."}
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

        match self.exec_type:
            case "exe":
                return self.__launch_exe()
            case "msi":
                return self.__launch_msi()
            case "batch":
                return self.__launch_batch()
            case _:
                logging.error(f"exec_type {self.exec_type} is not valid")
                return Result(
                    status=False, data={"message": "Unknown executable type."}
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
            environment=self.environment,
            communicate=True,
            pre_script=self.pre_script,
            post_script=self.post_script,
            cwd=self.cwd,
            midi_soundfont=self.midi_soundfont,
        )
        res = winecmd.run()
        self.__set_monitors()
        return Result(status=True, data={"output": res})

    def __launch_msi(self):
        msiexec = MsiExec(self.config)
        msiexec.install(
            pkg_path=self.exec_path,
            args=self.args,
            terminal=self.terminal,
            cwd=self.cwd,
            environment=self.environment,
        )
        self.__set_monitors()
        return Result(True)

    def __launch_batch(self):
        cmd = CMD(self.config)
        res = cmd.run_batch(
            batch=self.exec_path,
            terminal=self.terminal,
            args=self.args,
            environment=self.environment,
            cwd=self.cwd,
        )
        return Result(status=True, data={"output": res})

    def __launch_with_starter(self):
        start = Start(self.config)
        res = start.run(
            file=self.exec_path,
            terminal=self.terminal,
            args=self.args,
            environment=self.environment,
            pre_script=self.pre_script,
            post_script=self.post_script,
            cwd=self.cwd,
            midi_soundfont=self.midi_soundfont,
        )
        self.__set_monitors()
        return Result(status=True, data={"output": res})

    def __launch_with_explorer(self):
        w, h = self.config.Parameters.virtual_desktop_res.split("x")
        start = Explorer(self.config)
        res = start.launch_desktop(
            desktop=str(uuid.uuid4()),
            width=w,
            height=h,
            program=self.exec_path,
            args=self.args,
            environment=self.environment,
            cwd=self.cwd,
        )
        self.__set_monitors()
        return Result(status=res.status, data={"output": res.data})

    @staticmethod
    def __launch_dll():
        logging.warning("DLLs are not supported yet.")
        return Result(status=False, data={"error": "DLLs are not supported yet."})

    def __set_monitors(self):
        if not self.monitoring:
            return

        logging.info(f"Starting {len(self.monitoring)} monitors")

        winedbg = WineDbg(self.config, silent=True)
        for m in self.monitoring:
            winedbg.wait_for_process(name=m)
