import re
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
        component: str = "",
        custom_path: str = ""
    ) -> bool:
        logging.info("Opening the file manager in the path …")

        if path_type == "bottle":
            bottle_path = self.get_bottle_path(config)
            path = f"{bottle_path}/drive_c"

        if component != "":
            if path_type == "runner":
                path = self.get_runner_path(component)

            if path_type == "dxvk":
                path = self.get_dxvk_path(component)

            if path_type == "vkd3d":
                path = self.get_vkd3d_path(component)

            if path_type == "nvapi":
                path = self.get_nvapi_path(component)

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
    ):
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
    ):
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

    def run_wineboot(self, config: BottleConfig):
        logging.info("Running wineboot on the wineprefix …")
        RunAsync(self.run_command, None, config, "wineboot -u")

    def run_winecfg(self, config: BottleConfig):
        logging.info("Running winecfg on the wineprefix …")
        RunAsync(self.run_command, None, config, "winecfg")

    def run_winetricks(self, config: BottleConfig):
        logging.info("Running winetricks on the wineprefix …")
        RunAsync(self.run_command, None, config, "winetricks")

    def run_debug(self, config: BottleConfig):
        logging.info("Running a debug console on the wineprefix …")
        RunAsync(self.run_command, None, config, "winedbg", True)

    def run_cmd(self, config: BottleConfig):
        logging.info("Running a CMD on the wineprefix …")
        RunAsync(self.run_command, None, config, "cmd", True)

    def run_taskmanager(self, config: BottleConfig):
        logging.info("Running a Task Manager on the wineprefix …")
        RunAsync(self.run_command, None, config, "taskmgr")

    def run_controlpanel(self, config: BottleConfig):
        logging.info("Running a Control Panel on the wineprefix …")
        RunAsync(self.run_command, None, config, "control")

    def run_uninstaller(self, config: BottleConfig, uuid: str = False):
        logging.info("Running an Uninstaller on the wineprefix …")

        command = "uninstaller"
        if uuid:
            command = f"uninstaller --remove '{uuid}'"
        RunAsync(self.run_command, None, config, command)

    def run_regedit(self, config: BottleConfig):
        logging.info("Running a Regedit on the wineprefix …")
        RunAsync(self.run_command, None, config, "regedit")

    # Send status to a bottle
    def send_status(self, config: BottleConfig, status: str):
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
        path = config.get("Path")
        runner = config.get("Runner")
        arch = config.get("Arch")

        if "FLATPAK_ID" in os.environ \
                or "SNAP" in os.environ \
                or not UtilsTerminal().check_support() \
                and terminal:
            '''
            Work around for Flatpak and Snap not able to 
            use system host commands. Disable terminal to
            force the wineconsole, then append the comamnd
            as arguments.
            '''
            terminal = False
            if command in ["winedbg", "cmd"]:
                command = f"wineconsole {command}"

        if not cwd:
            '''
            If no cwd is given, use the WorkingDir from the
            bottle configuration.
            '''
            cwd = config.get("WorkingDir")
        if cwd == "":
            '''
            If the WorkingDir is empty, use the bottle path as
            working directory.
            '''
            cwd = self.get_bottle_path(config)

        if runner is None:
            '''
            If there is no runner declared in the bottle
            configuration, return None.
            '''
            return

        if runner.startswith("Proton"):
            '''
            If the runner is Proton, set the pat to /dist or /files 
            based on check if files exists.
            '''
            runner = "%s/files" % runner
            if os.path.exists("%s/%s/dist" % (Paths.runners, runner)):
                runner = "%s/dist" % runner

        if runner.startswith("sys-"):
            '''
            If the runner type is system, set the runner binary
            path to the system command. Else set it to the full path.
            '''
            runner = "wine"
        else:
            runner = f"{Paths.runners}/{runner}/bin/wine"

        if not config.get("Custom_Path"):
            path = "%s/%s" % (Paths.bottles, path)

        # Check for executable args from bottle config
        env = os.environ.copy()
        dll_overrides = []
        parameters = config["Parameters"]

        if config.get("DLL_Overrides"):
            for dll in config.get("DLL_Overrides").items():
                dll_overrides.append("%s=%s" % (dll[0], dll[1]))

        if parameters["environment_variables"]:
            for env_var in re.findall(
                r'(?:[^\s,"]|"(?:\\.|[^"])*"|\'(?:\\.|[^\'])*\')+',
                parameters["environment_variables"]
            ):
                key, value = env_var.split("=")
                env[key] = value

        if environment:
            if environment.get("WINEDLLOVERRIDES"):
                dll_overrides.append(environment["WINEDLLOVERRIDES"])
                del environment["WINEDLLOVERRIDES"]
            for e in environment:
                e = e.split("=")
                env[e[0]] = e[1]

        if parameters["dxvk"]:
            env["WINE_LARGE_ADDRESS_AWARE"] = "1"
            env["DXVK_STATE_CACHE_PATH"] = path
            env["STAGING_SHARED_MEMORY"] = "1"
            env["__GL_DXVK_OPTIMIZATIONS"] = "1"
            env["__GL_SHADER_DISK_CACHE"] = "1"
            env["__GL_SHADER_DISK_CACHE_PATH"] = path

        if parameters["dxvk_hud"]:
            env["DXVK_HUD"] = "devinfo,memory,drawcalls,fps,version,api,compiler"
        else:
            env["DXVK_HUD"] = "compiler"

        if parameters["sync"] == "esync":
            env["WINEESYNC"] = "1"

        if parameters["sync"] == "fsync":
            env["WINEFSYNC"] = "1"

        if parameters["fixme_logs"]:
            env["WINEDEBUG"] = "+fixme-all"
        else:
            env["WINEDEBUG"] = "fixme-all"

        if parameters["aco_compiler"]:
            env["ACO_COMPILER"] = "aco"

        if parameters["fsr"]:
            env["WINE_FULLSCREEN_FSR"] = "1"
            env["WINE_FULLSCREEN_FSR_STRENGHT"] = str(parameters["fsr_level"])

        if "WAYLAND_DISPLAY" in os.environ:
            # workaround https://github.com/bottlesdevs/Bottles/issues/419
            logging.info("Using Xwayland..")
            display = os.environ.get("DISPLAY", ":0")
            env["DISPLAY"] = display
            env["GDK_BACKEND"] = "x11"
            env["GDK_SDISPLAYALE"] = display

        if parameters["discrete_gpu"]:
            if "nvidia" in subprocess.Popen(
                "lspci | grep 'VGA'",
                stdout=subprocess.PIPE,
                shell=True
            ).communicate()[0].decode("utf-8").lower():
                env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
                env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
                env["__VK_LAYER_NV_optimus"] = "NVIDIA_only"
            else:
                env["DRI_PRIME"] = "1"

        if parameters["pulseaudio_latency"]:
            env["PULSE_LATENCY_MSEC"] = "60"

        env["WINEDLLOVERRIDES"] = ";".join(dll_overrides)
        env["WINEPREFIX"] = path
        env["WINEARCH"] = arch

        command = f"{runner} {command}"

        if arguments:
            if "%command%" in arguments:
                prefix = arguments.split("%command%")[0]
                suffix = arguments.split("%command%")[1]
                command = f"{prefix} {command} {suffix}"
            else:
                command = f"{command} {arguments}"

        if gamemode_available and config["Parameters"]["gamemode"]:
            # check for gamemode enabled
            command = f"gamemoderun {command}"

        if terminal:
            return UtilsTerminal().execute(command, env)
            
        if comunicate:
            try:
                return subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    shell=True,
                    env=env,
                    cwd=cwd
                ).communicate()[0].decode("utf-8")
            except:
                '''
                If return an exception, try to execute the command
                without the cwd argument
                '''
                return subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    shell=True,
                    env=env
                ).communicate()[0].decode("utf-8")

        try:
            '''
            If the comunicate flag is not set, still try to execute the
            command in comunicate mode, then read the output to catch the
            wine ShellExecuteEx exception, so we can raise it as a bottles
            exception and handle it in other parts of the code.
            '''
            res = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                cwd=cwd,
                shell=True,
                env=env
            ).communicate()[0].decode("utf-8")

            if "ShellExecuteEx" in res:
                raise Exception("ShellExecuteEx")
        except Exception as e:
            # workaround for `No such file or directory` error
            res = subprocess.Popen(command, shell=True, env=env)
            if comunicate:
                return res.communicate()
            return res

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

    @staticmethod
    def get_nvapi_path(nvapi: str) -> str:
        return f"{Paths.nvapi}/{nvapi}"
