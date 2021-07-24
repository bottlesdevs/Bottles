import os
import subprocess

from typing import NewType

from .utils import UtilsTerminal, UtilsLogger, RunAsync
from .runner_globals import BottlesPaths, gamemode_available

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)


class RunnerUtilities:

    # Open file manager in different paths
    def open_filemanager(self, configuration: BottleConfig = dict, path_type: str = "bottle", runner: str = "", dxvk: str = "", vkd3d: str = "", custom_path: str = "") -> bool:
        logging.info("Opening the file manager in the path …")

        if path_type == "bottle":
            path = "%s/%s/drive_c" % (BottlesPaths.bottles,
                                      configuration.get("Path"))

        if path_type == "runner" and runner != "":
            path = "%s/%s" % (BottlesPaths.runners, runner)

        if path_type == "dxvk" and dxvk != "":
            path = "%s/%s" % (BottlesPaths.dxvk, dxvk)

        if path_type == "vkd3d" and vkd3d != "":
            path = "%s/%s" % (BottlesPaths.vkd3d, vkd3d)

        if path_type == "custom" and custom_path != "":
            path = custom_path

        command = "xdg-open %s" % path
        return subprocess.Popen(command, shell=True).communicate()

    # Run .lnk files in a bottle
    def run_lnk(self, configuration: BottleConfig, file_path: str, arguments: str = False, environment: dict = False) -> None:
        logging.info("Running link file on the bottle …")
        command = f"start /unix '{file_path}'"
        RunAsync(self.run_command, None, configuration,
                 command, False, environment)

    # Run wine executables/programs in a bottle
    def run_executable(self, configuration: BottleConfig, file_path: str, arguments: str = False, environment: dict = False, no_async: bool = False) -> None:
        logging.info("Running an executable on the bottle …")

        if "msi" in file_path.split("."):
            command = "msiexec /i '%s'" % file_path
        elif "bat" in file_path.split("."):
            command = "wineconsole cmd /c '%s'" % file_path
        else:
            command = "'%s'" % file_path

        if arguments:
            command = "%s %s" % (command, arguments)

        if no_async:
            self.run_command(configuration, command, False, environment, True)
        else:
            RunAsync(self.run_command, None, configuration,
                    command, False, environment)

    def run_wineboot(self, configuration: BottleConfig) -> None:
        logging.info("Running wineboot on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "wineboot -u")

    def run_winecfg(self, configuration: BottleConfig) -> None:
        logging.info("Running winecfg on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "winecfg")

    def run_winetricks(self, configuration: BottleConfig) -> None:
        logging.info("Running winetricks on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "winetricks")

    def run_debug(self, configuration: BottleConfig) -> None:
        logging.info("Running a debug console on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "winedbg", True)

    def run_cmd(self, configuration: BottleConfig) -> None:
        logging.info("Running a CMD on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "cmd", True)

    def run_taskmanager(self, configuration: BottleConfig) -> None:
        logging.info("Running a Task Manager on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "taskmgr")

    def run_controlpanel(self, configuration: BottleConfig) -> None:
        logging.info("Running a Control Panel on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "control")

    def run_uninstaller(self, configuration: BottleConfig, uuid: str = False) -> None:
        logging.info("Running an Uninstaller on the wineprefix …")
        command = "uninstaller"
        if uuid:
            command = f"uninstaller --remove '{uuid}'"
        RunAsync(self.run_command, None, configuration, command)

    def run_regedit(self, configuration: BottleConfig) -> None:
        logging.info("Running a Regedit on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "regedit")

    # Send status to a bottle
    def send_status(self, configuration:BottleConfig, status:str) -> None:
        logging.info(f"Sending Status: [{status}] to the wineprefix …")

        available_status = {
            "shutdown": "-s",
            "reboot": "-r",
            "kill": "-k"
        }

        option = available_status[status]
        bottle_name = configuration.get("Name")

        self.run_command(configuration, "wineboot %s" % option)

    # Execute command in a bottle
    def run_command(self, configuration: BottleConfig, command: str, terminal: bool = False, environment: dict = False, comunicate: bool = False) -> bool:
        if "IS_FLATPAK" in os.environ or "SNAP" in os.environ and terminal:
            terminal = False
            if command in ["winedbg", "cmd"]:
                command = f"wineconsole {command}"

        path = configuration.get("Path")
        runner = configuration.get("Runner")

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
            runner = "%s/%s/bin/wine64" % (BottlesPaths.runners, runner)

        if not configuration.get("Custom_Path"):
            path = "%s/%s" % (BottlesPaths.bottles, path)

        # Check for executable args from bottle configuration
        environment_vars = []
        dll_overrides = []
        parameters = configuration["Parameters"]

        if configuration.get("DLL_Overrides"):
            for dll in configuration.get("DLL_Overrides").items():
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

        command = "WINEPREFIX={path} WINEARCH=win64 {env} {runner} {command}".format(
            path=path,
            env=environment_vars,
            runner=runner,
            command=command
        )

        # Check for gamemode enabled
        if gamemode_available and configuration["Parameters"]["gamemode"]:
            command = f"gamemoderun {command}"

        if terminal:
            return UtilsTerminal(command)

        if comunicate:
            return subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                shell=True,
                cwd=self.get_bottle_path(configuration)).communicate()[0].decode("utf-8")

        # TODO: configure cwd in bottle configuration
        return subprocess.Popen(
            command, 
            shell=True,
            cwd=self.get_bottle_path(configuration)).communicate()

    # Get bottle path by configuration
    def get_bottle_path(self, configuration:BottleConfig) -> str:
        if configuration.get("Custom_Path"):
            return configuration.get("Path")
        return "%s/%s" % (BottlesPaths.bottles, configuration.get("Path"))
    
