import os
import subprocess

from typing import NewType

from ..utils import UtilsTerminal, UtilsLogger, RunAsync
from .globals import Paths, gamemode_available

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)


class Runner:

    # Open file manager in different paths
    def open_filemanager(
        self,
        config: BottleConfig = dict,
        path_type: str = "bottle",
        runner: str = "",
        dxvk: str = "",
        vkd3d: str = "",
        custom_path: str = ""
    ) -> bool:
        logging.info("Opening the file manager in the path …")

        if path_type == "bottle":
            bottle_path = self.get_bottle_path(config)
            path = f"{bottle_path}/drive_c"

        if path_type == "runner" and runner != "":
            path = self.get_runner_path(runner)

        if path_type == "dxvk" and dxvk != "":
            path = self.get_dxvk_path(dxvk)

        if path_type == "vkd3d" and vkd3d != "":
            path = self.get_vkd3d_path(vkd3d)

        if path_type == "custom" and custom_path != "":
            path = custom_path

        command = f"xdg-open '{path}'"
        return subprocess.Popen(command, shell=True).communicate()

    # Run .lnk files in a bottle
    def run_lnk(
        self,
        config: BottleConfig,
        file_path: str,
        arguments: str = "",
        environment: dict = False
    ) -> None:
        logging.info("Running link file on the bottle …")
        
        command = f"start /unix '{file_path}'"
        RunAsync(self.run_command, None, config,
                 command, False, arguments, environment)

    # Run wine executables/programs in a bottle
    def run_executable(
        self,
        config: BottleConfig,
        file_path: str,
        arguments: str = "",
        environment: dict = False,
        no_async: bool = False,
        cwd: str = None
    ) -> None:
        logging.info("Running an executable on the bottle …")
        
        command = f"'{file_path}'"

        if "msi" in file_path.split("."):
            command = f"msiexec /i '{file_path}'"
        elif "bat" in file_path.split("."):
            command = f"wineconsole cmd /c '{file_path}'"

        if no_async:
            self.run_command(config, command,
                             False, arguments, environment, True, cwd)
        else:
            RunAsync(self.run_command, None, config,
                     command, False, arguments, environment, False, cwd)

    def run_wineboot(self, config: BottleConfig) -> None:
        logging.info("Running wineboot on the wineprefix …")
        RunAsync(self.run_command, None, config, "wineboot -u")

    def run_winecfg(self, config: BottleConfig) -> None:
        logging.info("Running winecfg on the wineprefix …")
        RunAsync(self.run_command, None, config, "winecfg")

    def run_winetricks(self, config: BottleConfig) -> None:
        logging.info("Running winetricks on the wineprefix …")
        RunAsync(self.run_command, None, config, "winetricks")

    def run_debug(self, config: BottleConfig) -> None:
        logging.info("Running a debug console on the wineprefix …")
        RunAsync(self.run_command, None, config, "winedbg", True)

    def run_cmd(self, config: BottleConfig) -> None:
        logging.info("Running a CMD on the wineprefix …")
        RunAsync(self.run_command, None, config, "cmd", True)

    def run_taskmanager(self, config: BottleConfig) -> None:
        logging.info("Running a Task Manager on the wineprefix …")
        RunAsync(self.run_command, None, config, "taskmgr")

    def run_controlpanel(self, config: BottleConfig) -> None:
        logging.info("Running a Control Panel on the wineprefix …")
        RunAsync(self.run_command, None, config, "control")

    def run_uninstaller(self, config: BottleConfig, uuid: str = False):
        logging.info("Running an Uninstaller on the wineprefix …")
        
        command = "uninstaller"
        if uuid:
            command = f"uninstaller --remove '{uuid}'"
        RunAsync(self.run_command, None, config, command)

    def run_regedit(self, config: BottleConfig) -> None:
        logging.info("Running a Regedit on the wineprefix …")
        RunAsync(self.run_command, None, config, "regedit")

    # Send status to a bottle
    def send_status(self, config: BottleConfig, status: str) -> None:
        logging.info(f"Sending Status: [{status}] to the wineprefix …")

        available_status = {
            "shutdown": "-s",
            "reboot": "-r",
            "kill": "-k"
        }
        option = available_status[status]
        self.run_command(config, "wineboot %s" % option)

    # Execute command in a bottle
    def run_command(
        self,
        config: BottleConfig,
        command: str,
        terminal: bool = False,
        arguments: str = False,
        environment: dict = False,
        comunicate: bool = False,
        cwd: str = None
    ) -> bool:
        # Work around for Flatpak and Snap not able to use system commands
        if "FLATPAK_ID" in os.environ \
            or "SNAP" in os.environ \
            or not UtilsTerminal().check_support() \
            and terminal:
            terminal = False
            if command in ["winedbg", "cmd"]:
                command = f"wineconsole {command}"

        if not cwd:
            cwd = config.get("WorkingDir")
        if cwd == "":
            cwd = self.get_bottle_path(config)
        
        path = config.get("Path")
        runner = config.get("Runner")
        arch = config.get("Arch")
        
        if runner is None:
            return

        # If runner is proton then set path to /dist
        if runner.startswith("Proton"):
            if os.path.exists("%s/%s/dist" % (Paths.runners, runner)):
                runner = "%s/dist" % runner
            else:
                runner = "%s/files" % runner

        # If runner is system
        if runner.startswith("sys-"):
            runner = "wine"
        else:
            runner = f"{Paths.runners}/{runner}/bin/wine"

        if not config.get("Custom_Path"):
            path = "%s/%s" % (Paths.bottles, path)

        # Check for executable args from bottle config
        environment_vars = []
        dll_overrides = []
        parameters = config["Parameters"]

        if config.get("DLL_Overrides"):
            for dll in config.get("DLL_Overrides").items():
                dll_overrides.append("%s=%s" % (dll[0], dll[1]))

        if parameters["environment_variables"]:
            environment_vars.append(parameters["environment_variables"])

        if environment:
            if environment.get("WINEDLLOVERRIDES"):
                dll_overrides.append(environment["WINEDLLOVERRIDES"])
                del environment["WINEDLLOVERRIDES"]
            for e in environment:
                environment_vars.append(e)

        if parameters["dxvk"]:
            # dll_overrides.append("d3d11,dxgi=n")
            environment_vars.append("WINE_LARGE_ADDRESS_AWARE=1")
            environment_vars.append("DXVK_STATE_CACHE_PATH='%s'" % path)
            environment_vars.append("STAGING_SHARED_MEMORY=1")
            environment_vars.append("__GL_DXVK_OPTIMIZATIONS=1")
            environment_vars.append("__GL_SHADER_DISK_CACHE=1")
            environment_vars.append("__GL_SHADER_DISK_CACHE_PATH='%s'" % path)

        if parameters["dxvk_hud"]:
            environment_vars.append(
                "DXVK_HUD='devinfo,memory,drawcalls,fps,version,api,compiler'")
        else:
            environment_vars.append("DXVK_HUD='compiler'")

        if parameters["sync"] == "esync":
            environment_vars.append("WINEESYNC=1")  # WINEDEBUG=+esync

        if parameters["sync"] == "fsync":
            environment_vars.append("WINEFSYNC=1")

        if parameters["fixme_logs"]:
            environment_vars.append("WINEDEBUG=+fixme-all")
        else:
            environment_vars.append("WINEDEBUG=fixme-all")

        if parameters["aco_compiler"]:
            environment_vars.append("RADV_PERFTEST=aco")

        if "WAYLAND_DISPLAY" in os.environ:
            # workaround https://github.com/bottlesdevs/Bottles/issues/419
            logging.info("Using Xwayland..")
            display = os.environ.get("DISPLAY", ":0")
            environment_vars.append("GDK_BACKEND=x11")
            environment_vars.append(f"DISPLAY={display}")

        if parameters["discrete_gpu"]:
            if "nvidia" in subprocess.Popen(
                    "lspci | grep 'VGA'",
                    stdout=subprocess.PIPE,
                    shell=True).communicate()[0].decode("utf-8").lower():
                environment_vars.append("__NV_PRIME_RENDER_OFFLOAD=1")
                environment_vars.append("__GLX_VENDOR_LIBRARY_NAME='nvidia'")
                environment_vars.append("__VK_LAYER_NV_optimus='NVIDIA_only'")
            else:
                environment_vars.append("DRI_PRIME=1")

        if parameters["pulseaudio_latency"]:
            environment_vars.append("PULSE_LATENCY_MSEC=60")

        environment_vars.append("WINEDLLOVERRIDES='%s'" %
                                ";".join(dll_overrides))
        environment_vars = " ".join(environment_vars)

        command = f"WINEPREFIX={path} "\
            f"WINEARCH={arch} {environment_vars} {runner} {command}"

        if arguments:
            if "%command%" in arguments:
                prefix = arguments.split("%command%")[0]
                suffix = arguments.split("%command%")[1]
                command = f"{prefix} {command} {suffix}"

        # Check for gamemode enabled
        if gamemode_available and config["Parameters"]["gamemode"]:
            command = f"gamemoderun {command}"

        if terminal:
            return UtilsTerminal().execute(command)

        if comunicate:
            try:
                return subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    shell=True,
                    cwd=cwd
                ).communicate()[0].decode("utf-8")
            except:
                # workaround for `No such file or directory` error
                return subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    shell=True
                ).communicate()[0].decode("utf-8")

        # TODO: configure cwd in bottle config
        try:
            res = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    cwd=cwd,
                    shell=True
            ).communicate()[0].decode("utf-8")
            if "ShellExecuteEx" in res:
                raise Exception("ShellExecuteEx")
        except Exception as e:
            # workaround for `No such file or directory` error
            return subprocess.Popen(command, shell=True).communicate()

    @staticmethod
    def get_bottle_path(config: BottleConfig) -> str:
        if config.get("Custom_Path"):
            return config.get("Path")
        return f"{Paths.bottles}/{config.get('Path')}"

    @staticmethod
    def get_runner_path(runner: str) -> str:
        return f"{Paths.runners}/{runner}"

    @staticmethod
    def get_dxvk_path(dxvk: str) -> str:
        return f"{Paths.dxvk}/{dxvk}"

    @staticmethod
    def get_vkd3d_path(vkd3d: str) -> str:
        return f"{Paths.vkd3d}/{vkd3d}"