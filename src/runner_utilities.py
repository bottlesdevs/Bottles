import os
import subprocess
from libwine.wine import Wine

from typing import NewType

from .utils import UtilsTerminal, UtilsLogger, RunAsync
from .runner_globals import BottlesPaths, gamemode_available

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)


class RunnerUtilities:

    def __init__(self, configuration: BottleConfig = None):
        self.wine = None
        if configuration not in [None, str]:
            self.wine = Wine(
                winepath=self.get_runner_path(configuration.get('Runner')),
                wineprefix=self.get_bottle_path(configuration)
            )
            self.configuration = configuration

    # Open file manager in different paths
    def open_filemanager(
        self,
        configuration: BottleConfig = None,
        path_type: str = "bottle",
        runner: str = "",
        dxvk: str = "",
        vkd3d: str = "",
        custom_path: str = ""
    ) -> bool:
        logging.info("Opening the file manager in the path …")

        if configuration is None and self.configuration is not None:
            configuration = self.configuration
        else:
            raise ValueError("No configuration found")
            
        if path_type == "bottle":
            bottle_path = self.get_bottle_path(configuration)
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
        configuration: BottleConfig,
        file_path: str,
        arguments: str = False,
        environment: dict = False
    ):
        logging.info("Running link file on the bottle …")

        command = f"start /unix '{file_path}'"
        RunAsync(self.run_command, None, configuration,
                 command, False, environment)

    # Run wine executables/programs in a bottle
    def run_executable(
        self,
        file_path: str,
        arguments: str = False,
        environment: dict = False,
        no_async: bool = False,
        cwd: str = None
    ):
        logging.info("Running an executable on the bottle …")

        command = f"'{file_path}'"

        if "msi" in file_path.split("."):
            command = f"msiexec /i '{file_path}'"
        elif "bat" in file_path.split("."):
            command = f"wineconsole cmd /c '{file_path}'"

        if arguments:
            command = f"{command} {arguments}"

        if no_async:
            self.run_command(command, False, environment, True, cwd)
        else:
            RunAsync(self.run_command, None, command, False, environment, False, cwd)

    def run_winecfg(self, widget: None):
        logging.info("Running winecfg on the wineprefix …")
        RunAsync(self.wine.winecfg, None)

    def run_debug(self, widget=None):
        logging.info("Running a CMD on the wineprefix …")
        terminal = UtilsTerminal.get_terminal()

        if "IS_FLATPAK" in os.environ or "SNAP" in os.environ or terminal is None:
            RunAsync(self.wine.debug, None, None, True)
            return

        RunAsync(self.wine.debug, None, terminal)

    def run_cmd(self, widget=None):
        logging.info("Running a CMD on the wineprefix …")
        terminal = UtilsTerminal.get_terminal()

        if "IS_FLATPAK" in os.environ or "SNAP" in os.environ or terminal is None:
            RunAsync(self.wine.cmd, None, None, True)
            return

        RunAsync(self.wine.cmd, None, terminal)

    def run_taskmanager(self, widget=None):
        logging.info("Running a Task Manager on the wineprefix …")
        RunAsync(self.wine.taskmanager, None)

    def run_controlpanel(self, widget=None):
        logging.info("Running a Control Panel on the wineprefix …")
        RunAsync(self.wine.controlpanel, None)

    def run_uninstaller(self, widget=None, uuid: str = None):
        logging.info("Running an Uninstaller on the wineprefix …")
        RunAsync(self.wine.uninstaller, None, uuid)

    def run_regedit(self, widget=None):
        logging.info("Running a Regedit on the wineprefix …")
        RunAsync(self.wine.regedit, None)

    # Send status to a bottle
    def run_kill(self, widget=None):
        logging.info("Running a kill on the wineprefix …")
        RunAsync(self.wine.kill, None)

    def run_restart(self, widget=None):
        logging.info("Running a restart on the wineprefix …")
        RunAsync(self.wine.restart, None)

    def run_shutdown(self, widget=None):
        logging.info("Running a shutdown on the wineprefix …")
        RunAsync(self.wine.shutdown, None)

    def run_update(self, widget=None):
        logging.info("Running an update on the wineprefix …")
        RunAsync(self.wine.update, None)

    # Execute command in a bottle
    def run_command(
        self,
        command: str,
        terminal: bool = False,
        environment: dict = False,
        comunicate: bool = False,
        cwd: str = None
    ) -> bool:
        if terminal:
            terminal = UtilsTerminal.get_terminal()
            
        # Work around for Flatpak and Snap not able to use system commands
        if "IS_FLATPAK" in os.environ or "SNAP" in os.environ and terminal:
            terminal = False
            if command in ["winedbg", "cmd"]:
                command = f"wineconsole {command}"

        if not cwd:
            cwd = self.get_bottle_path(self.configuration)

        path = self.configuration.get("Path")
        runner = self.configuration.get("Runner")
        arch = self.configuration.get("Arch")

        # If runner is proton then set path to /dist
        if runner.startswith("Proton"):
            if os.path.exists("%s/%s/dist" % (BottlesPaths.runners, runner)):
                runner = "%s/dist" % runner
            else:
                runner = "%s/files" % runner

        # If runner is system
        if runner.startswith("sys-"):
            runner = "wine"
        else:
            runner = f"{BottlesPaths.runners}/{runner}/bin/wine"

        if not self.configuration.get("Custom_Path"):
            path = "%s/%s" % (BottlesPaths.bottles, path)

        # Check for executable args from bottle configuration
        environment_vars = {}
        dll_overrides = []
        parameters = self.configuration["Parameters"]

        if self.configuration.get("DLL_Overrides"):
            for dll in self.configuration.get("DLL_Overrides").items():
                dll_overrides.append("%s=%s" % (dll[0], dll[1]))

        if parameters["environment_variables"]:
            environment_vars.append(parameters["environment_variables"])

        if environment:
            if environment.get("WINEDLLOVERRIDES"):
                dll_overrides.append(environment["WINEDLLOVERRIDES"])
                del environment["WINEDLLOVERRIDES"]
            for e in environment:
                environment_vars[e] = environment[e]

        if parameters["dxvk"]:
            # dll_overrides.append("d3d11,dxgi=n")
            environment_vars["WINE_LARGE_ADDRESS_AWARE"] = "1"
            environment_vars["DXVK_STATE_CACHE_PATH"] = f"'{path}'"
            environment_vars["STAGING_SHARED_MEMORY"] = "1"
            environment_vars["__GL_DXVK_OPTIMIZATIONS"] = "1"
            environment_vars["__GL_SHADER_DISK_CACHE"] = "1"
            environment_vars["__GL_SHADER_DISK_CACHE_PATH"] = f"'{path}'"

        if parameters["dxvk_hud"]:
            environment_vars["DXVK_HUD"] = "'devinfo,memory,drawcalls,fps,version,api,compiler'"
        else:
            environment_vars["DXVK_HUD"] = "'compiler'"

        if parameters["sync"] == "esync":
            environment_vars["WINEESYNC"] = "1" # WINEDEBUG=+esync

        if parameters["sync"] == "fsync":
            environment_vars["WINEFSYNC"] = "1"

        if parameters["fixme_logs"]:
            environment_vars["WINEDEBUG"] = "+fixme-all"
        else:
            environment_vars["WINEDEBUG"] = "fixme-all"

        if parameters["aco_compiler"]:
            environment_vars["RADV_PERFTEST"] = "aco"

        if "WAYLAND_DISPLAY" in os.environ:
            # workaround https://github.com/bottlesdevs/Bottles/issues/419
            environment_vars["DISPLAY"] = ":0"

        if parameters["discrete_gpu"]:
            if "nvidia" in subprocess.Popen(
                    "lspci | grep 'VGA'",
                    stdout=subprocess.PIPE,
                    shell=True).communicate()[0].decode("utf-8").lower():
                environment_vars["__NV_PRIME_RENDER_OFFLOAD"] = "1"
                environment_vars["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
                environment_vars["__VK_LAYER_NV_optimus"] = "NVIDIA_only"
            else:
                environment_vars["DRI_PRIME"] = "1"

        if parameters["pulseaudio_latency"]:
            environment_vars["PULSE_LATENCY_MSEC"] = "60"

        environment_vars["WINEDLLOVERRIDES"] = ";".join(dll_overrides)
        environment_vars["WINEARCH"] = arch

        '''TODO: Gamemode is not supported by libwine
        if gamemode_available and self.configuration["Parameters"]["gamemode"]:
            command = f"gamemoderun {command}"
        '''

        try:
            self.wine.execute(
                command=command,
                comunicate=comunicate,
                envs=environment_vars,
                terminal=terminal,
                cwd=cwd
            )
        except:
            self.wine.execute(
                command=command,
                comunicate=comunicate,
                envs=environment_vars,
                terminal=terminal
            )

    @staticmethod
    def get_bottle_path(configuration: BottleConfig) -> str:
        if configuration.get("Custom_Path"):
            return configuration.get("Path")
        return f"{BottlesPaths.bottles}/{configuration.get('Path')}"

    @staticmethod
    def get_runner_path(runner: str) -> str:
        return f"{BottlesPaths.runners}/{runner}"

    @staticmethod
    def get_dxvk_path(dxvk: str) -> str:
        return f"{BottlesPaths.dxvk}/{dxvk}"

    @staticmethod
    def get_vkd3d_path(vkd3d: str) -> str:
        return f"{BottlesPaths.vkd3d}/{vkd3d}"
