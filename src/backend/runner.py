import re
import os
import time
import shutil
import subprocess
from typing import NewType

from ..utils import UtilsTerminal, UtilsLogger, RunAsync
from .globals import Paths, gamemode_available
from .manager_utils import ManagerUtils

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class Runner:
    '''
    This class handle everything related to the runner (e.g. WINE, Proton).
    It should not contain any manager logic (e.g. catalogs, checks, etc.) or
    any bottle related stuff (e.g. config handling, etc.), also DXVK, VKD3D,
    NVAPI handling should not performed from here. This class should be kept
    as clean as possible to easily migrate to the libwine in the future.
    <https://github.com/bottlesdevs/libwine>
    '''

    _windows_versions = {
        "win10": {
            "ProductName": "Microsoft Windows 10",
            "CSDVersion": "",
            "CurrentBuild": "17763",
            "CurrentBuildNumber": "17763",
            "CurrentVersion": "10.0",
        },
        "win81": {
            "ProductName": "Microsoft Windows 8.1",
            "CSDVersion": "",
            "CurrentBuild": "9600",
            "CurrentBuildNumber": "9600",
            "CurrentVersion": "6.3",
        },
        "win8": {
            "ProductName": "Microsoft Windows 8",
            "CSDVersion": "",
            "CurrentBuild": "9200",
            "CurrentBuildNumber": "9200",
            "CurrentVersion": "6.2",
        },
        "win7": {
            "ProductName": "Microsoft Windows 7",
            "CSDVersion": "Service Pack 1",
            "CurrentBuild": "7601",
            "CurrentBuildNumber": "7601",
            "CurrentVersion": "6.1",
        },
        "win2008r2": {
            "ProductName": "Microsoft Windows 2008 R2",
            "CSDVersion": "Service Pack 1",
            "CurrentBuild": "7601",
            "CurrentBuildNumber": "7601",
            "CurrentVersion": "6.1",
        },
        "win2008": {
            "ProductName": "Microsoft Windows 2008",
            "CSDVersion": "Service Pack 2",
            "CurrentBuild": "6002",
            "CurrentBuildNumber": "6002",
            "CurrentVersion": "6.0",
        },
        "winxp": {
            "ProductName": "Microsoft Windows XP",
            "CSDVersion": "Service Pack 2",
            "CurrentBuild": "3790",
            "CurrentBuildNumber": "3790",
            "CurrentVersion": "5.2",
        },
    }

    @staticmethod
    def run_lnk(
        config: BottleConfig,
        file_path: str,
        arguments: str = "",
        environment: dict = False
    ):
        '''
        Run a .lnk file with arguments and environment variables, inside
        a bottle using the config provided.
        '''
        logging.info("Running link file on the bottle…")

        command = f"start /unix '{file_path}'"
        RunAsync(
            Runner.run_command, None, 
            config, command, False, arguments, environment
        )

    @staticmethod
    def run_executable(
        config: BottleConfig,
        file_path: str,
        arguments: str = "",
        environment: dict = False,
        no_async: bool = False,
        cwd: str = None
    ):
        '''
        Run an executable file with arguments and environment variables, inside
        a bottle using the config provided.
        '''
        logging.info("Running an executable on the bottle…")

        command = f"'{file_path}'"

        if "msi" in file_path.split("."):
            command = f"msiexec /i '{file_path}'"
        elif "bat" in file_path.split("."):
            command = f"wineconsole cmd /c '{file_path}'"

        if no_async:
            Runner.run_command(
                config, 
                command,
                terminal=False, 
                arguments=arguments, 
                environment=environment, 
                comunicate=True, 
                cwd=cwd
            )
        else:
            RunAsync(
                Runner.run_command, None, 
                config, command, False, arguments, environment, False, cwd
            )

    @staticmethod
    def run_winecfg(config: BottleConfig):
        logging.info("Running winecfg on the wineprefix…")
        RunAsync(Runner.run_command, None, config, "winecfg")

    @staticmethod
    def run_winetricks( config: BottleConfig):
        logging.info("Running winetricks on the wineprefix…")
        RunAsync(Runner.run_command, None, config, "winetricks")

    @staticmethod
    def run_debug(config: BottleConfig):
        logging.info("Running a debug console on the wineprefix…")
        RunAsync(Runner.run_command, None, config, "winedbg", True)

    @staticmethod
    def run_cmd(config: BottleConfig):
        logging.info("Running a CMD on the wineprefix…")
        RunAsync(Runner.run_command, None, config, "cmd", True)

    @staticmethod
    def run_taskmanager(config: BottleConfig):
        logging.info("Running a Task Manager on the wineprefix…")
        RunAsync(Runner.run_command, None, config, "taskmgr")

    @staticmethod
    def run_controlpanel( config: BottleConfig):
        logging.info("Running a Control Panel on the wineprefix…")
        RunAsync(Runner.run_command, None, config, "control")

    @staticmethod
    def run_uninstaller(config: BottleConfig, uuid: str = False):
        logging.info("Running an Uninstaller on the wineprefix…")
        command = "uninstaller"

        if uuid:
            command = f"uninstaller --remove '{uuid}'"
        RunAsync(Runner.run_command, None, config, command)

    @staticmethod
    def run_regedit(config: BottleConfig):
        logging.info("Running a Regedit on the wineprefix…")
        RunAsync(Runner.run_command, None, config, "regedit")

    @staticmethod
    def wineboot(
        config: BottleConfig, 
        status: int, 
        silent: bool = True, 
        comunicate: bool = False
    ):
        '''
        Manage Wine server uptime using wineboot, inside a bottle using the
        given configuraton.
        ---
        supported statues:
            - -1: force
            - 0: kill
            - 1: restart
            - 2: shutdown
            - 3: update
            - 4: init
        ---
        raises: ValueError
            if the status is not supported.
        '''
        states = {
            -1: "force",
            0: "-k",
            1: "-r",
            2: "-s",
            3: "-u",
            4: "-i"
        }
        envs = {"WINEDEBUG": "-all"}

        if status in states:
            status = states[status]
            command = f"wineboot {status}"
        
            if silent:
                envs["DISPLAY"] = ":3.0"
                command = f"{command} /nogui"
                
            Runner.run_command(
                config, 
                command, 
                environment=envs,
                comunicate=comunicate
            )
        else:
            raise ValueError(f"[{status}] is not a valid status for wineboot!")

    @staticmethod
    def run_command(
        config: BottleConfig,
        command: str,
        terminal: bool = False,
        arguments: str = False,
        environment: dict = False,
        comunicate: bool = False,
        cwd: str = None
    ):
        '''
        Run a command inside a bottle using the config provided, supports
        the comunicate argument to wait for the command to finish and
        catch the output.
        '''
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
            force the wineconsole, then append the command
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
            cwd = ManagerUtils.get_bottle_path(config)

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
        
        if arch == "win64":
            runner = f"{runner}64"

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
                try:
                    key, value = env_var.split("=")
                    env[key] = value
                except:
                    # ref: https://github.com/bottlesdevs/Bottles/issues/668
                    logging.debug(f"Invalid environment variable: {env_var}")

        if environment:
            if environment.get("WINEDLLOVERRIDES"):
                dll_overrides.append(environment["WINEDLLOVERRIDES"])
                del environment["WINEDLLOVERRIDES"]
            for e in environment:
                env[e] = environment[e]
            # for e in environment:
            #     e = e.split("=")
            #     env[e[0]] = e[1]

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

        if not env.get("WINEDEBUG"):
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
    def get_running_processes() -> list:
        '''
        This function gets all running WINE processes and returns
        them as a list of dictionaries.
        '''
        processes = []
        command = "ps -eo pid,pmem,pcpu,stime,time,cmd | grep wine | tr -s ' ' '|'"
        pids = subprocess.check_output(['bash', '-c', command]).decode("utf-8")

        for pid in pids.split("\n"):
            # workaround https://github.com/bottlesdevs/Bottles/issues/396
            if pid.startswith("|"):
                pid = pid[1:]

            process_data = pid.split("|")
            if len(process_data) >= 6 and "grep" not in process_data:
                processes.append({
                    "pid": process_data[0],
                    "pmem": process_data[1],
                    "pcpu": process_data[2],
                    "stime": process_data[3],
                    "time": process_data[4],
                    "cmd": process_data[5]
                })

        return processes

    @staticmethod
    def set_windows(config: BottleConfig, version: str):
        '''
        Change Windows version in a bottle from the given
        configuration.
        ----------
        supported versions:
            - win10 (Microsoft Windows 10)
            - win81 (Microsoft Windows 8.1)
            - win8 (Microsoft Windows 8)
            - win7 (Microsoft Windows 7)
            - win2008r2 (Microsoft Windows 2008 R1)
            - win2008 (Microsoft Windows 2008)
            - winxp (Microsoft Windows XP)
        ------
        raises: ValueError
            If the given version is invalid.
        '''

        if version not in Runner._windows_versions:
            raise ValueError("Given version is not supported.")

        Runner.reg_add(
            config=config,
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion",
            value="ProductName",
            data=Runner._windows_versions.get(version)["ProductName"]
        )

        Runner.reg_add(
            config=config,
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion",
            value="CSDVersion",
            data=Runner._windows_versions.get(version)["CSDVersion"]
        )

        Runner.reg_add(
            config=config,
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion",
            value="CurrentBuild",
            data=Runner._windows_versions.get(version)["CurrentBuild"]
        )

        Runner.reg_add(
            config=config,
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion",
            value="CurrentBuildNumber",
            data=Runner._windows_versions.get(version)["CurrentBuildNumber"]
        )

        Runner.reg_add(
            config=config,
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion",
            value="CurrentVersion",
            data=Runner._windows_versions.get(version)["CurrentVersion"]
        )

        Runner.wineboot(config, status=1, comunicate=True)
    
    @staticmethod
    def set_app_default(config: BottleConfig, version: str, executable: str):
        '''
        Change default Windows version per application in a bottle
        from the given configuration.
        ----------
        supported versions:
            - win10 (Microsoft Windows 10)
            - win81 (Microsoft Windows 8.1)
            - win8 (Microsoft Windows 8)
            - win7 (Microsoft Windows 7)
            - win2008r2 (Microsoft Windows 2008 R1)
            - win2008 (Microsoft Windows 2008)
            - winxp (Microsoft Windows XP)
        ------
        raises: ValueError
            If the given version is invalid.
        '''
        if version not in Runner._windows_versions:
            raise ValueError("Given version is not supported.")
            
        Runner.reg_add(
            config=config,
            key=f"HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\{executable}",
            value="Version",
            data=version
        )
    
    @staticmethod
    def reg_add(
        config: BottleConfig, 
        key: str, 
        value: str, 
        data: str, 
        keyType: str = False
    ):
        '''
        This function adds a value with its data in the given 
        bottle registry key.
        '''
        logging.info(
            f"Adding Key: [{key}] with Value: [{value}] and "
            f"Data: [{data}] in register bottle: {config['Name']}"
        )

        command = "reg add '%s' /v '%s' /d '%s' /f" % (key, value, data)
        
        if keyType:
            command = "reg add '%s' /v '%s' /t %s /d '%s' /f" % (
                key, value, keyType, data)
        
        Runner.wait_for_process(config, "reg.exe")
        res = Runner.run_command(config, command, comunicate=True)
        logging.info(res)

    @staticmethod
    def reg_delete(config: BottleConfig, key: str, value: str):
        '''
        This function deletes a value with its data in the given
        bottle registry key.
        '''
        logging.info(
            f"Removing Value: [{key}] for Key: [{value}] in "
            f"register bottle: {config['Name']}"
        )

        Runner.wait_for_process(config, "reg.exe")
        Runner.run_command(config, f"reg delete '{key}' /v {value} /f")

    @staticmethod
    def dll_override(
        config: BottleConfig,
        arch: str,
        dlls: list,
        source: str,
        revert: bool = False
    ) -> bool:
        '''
        This function replace a DLL in a bottle (this is not a wine
        DLL override). It also make a backup of the original DLL, that
        can be reverted with the revert option.
        '''
        arch = "system32" if arch == 32 else "syswow64"
        path = "{0}/{1}/drive_c/windows/{2}".format(
            Paths.bottles,
            config.get("Path"),
            arch
        )

        try:
            if revert:
                # restore the backup
                for dll in dlls:
                    shutil.move(
                        f"{path}/{dll}.back",
                        f"{path}/{dll}"
                    )
            else:
                for dll in dlls:
                    '''
                    for each DLL in the list, we create a backup of the
                    original one and replace it with the new one.
                    '''
                    shutil.move(
                        f"{path}/{dll}",
                        f"{path}/{dll}.back"
                    )
                    shutil.copy(
                        f"{source}/{dll}",
                        f"{path}/{dll}"
                    )
        except:
            return False
        return True

    @staticmethod
    def toggle_virtual_desktop(
        config: BottleConfig,
        state: bool,
        resolution: str = "800x600"
    ):
        '''
        This function toggles the virtual desktop for a bottle, updating
        the Desktops registry key.
        '''
        if state:
            Runner.reg_add(
                config,
                key="HKEY_CURRENT_USER\\Software\\Wine\\Explorer",
                value="Desktop",
                data="Default"
            )
            Runner.reg_add(
                config,
                key="HKEY_CURRENT_USER\\Software\\Wine\\Explorer\\Desktops",
                value="Default",
                data=resolution
            )
        else:
            Runner.reg_delete(
                config,
                key="HKEY_CURRENT_USER\\Software\\Wine\\Explorer",
                value="Desktop"
            )
        Runner.wineboot(config, status=3, comunicate=True)
    
    @staticmethod
    def get_processes(config:BottleConfig) -> list:
        '''
        Get processes running on the wineprefix as a list.
        '''
        processes = []
        parent = None

        winedbg = Runner.run_command(
            config,
            command='winedbg --command "info proc"',
            comunicate=True
        ).split("\n")

        # remove the first line from the output (the header)
        del winedbg[0]

        for w in winedbg:
            w = re.sub("\s{2,}", " ", w)[1:].replace("'", "")

            if "\_" in w:
                w = w.replace("\_ ", "")
                w += " child"

            w = w.split(" ")
            w_parent = None

            if len(w) >= 3 and w[1].isdigit():
                w_pid = w[0]
                w_threads = w[1]
                w_name = w[2]

                if len(w) == 3:
                    parent = w_pid
                else:
                    w_parent = parent

                w = {
                    "pid": w_pid,
                    "threads": w_threads,
                    "name": w_name,
                    "parent": w_parent
                }
                processes.append(w)

        return processes
    
    @staticmethod
    def wait_for_process(config:BottleConfig, name:str):
        '''
        Wait for a process to exit.
        '''
        while True:
            processes = Runner.get_processes(config)
            if len(processes) == 0:
                break
            if name not in [p["name"] for p in processes]:
                break
            time.sleep(1)
