import re
import os
import time
import shlex
import shutil
import subprocess
from typing import NewType

from ..utils import UtilsTerminal, UtilsLogger, RunAsync, detect_encoding
from .globals import Paths, CMDSettings, gamemode_available, x_display
from .manager_utils import ManagerUtils
from .runtime import RuntimeManager
from .display import DisplayUtils
from .gpu import GPUUtils
from .result import Result


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
            "CSDVersion": "",
            "CurrentBuildNumber": "10240",
            "CurrentVersion": "10.0",
            "CSDVersionHex": "00000000",
            "ProductType": "WinNT",
        },
        "win81": {
            "CSDVersion": "",
            "CurrentBuildNumber": "9600",
            "CurrentVersion": "6.3",
            "CSDVersionHex": "00000000",
            "ProductType": "WinNT",
        },
        "win8": {
            "CSDVersion": "",
            "CurrentBuildNumber": "9200",
            "CurrentVersion": "6.2",
            "CSDVersionHex": "00000000",
            "ProductType": "WinNT",
        },
        "win7": {
            "CSDVersion": "Service Pack 1",
            "CurrentBuildNumber": "7601",
            "CurrentVersion": "6.1",
            "CSDVersionHex": "00000100",
            "ProductType": "WinNT",
        },
        "win2008r2": {
            "CSDVersion": "Service Pack 1",
            "CurrentBuildNumber": "7601",
            "CurrentVersion": "6.1",
            "CSDVersionHex": "00000100",
            "ProductType": "WinNT",
        },
        "win2008": {
            "CSDVersion": "Service Pack 2",
            "CurrentBuildNumber": "6002",
            "CurrentVersion": "6.0",
            "CSDVersionHex": "00000200",
            "ProductType": "WinNT",
        },
        "winxp": {
            "CSDVersion": "Service Pack 3",
            "CurrentBuildNumber": "2600",
            "CSDVersionHex": "00000300",
            "CurrentVersion": "5.1",
        },
        "winxp64": {
            "CSDVersion": "Service Pack 2",
            "CurrentBuildNumber": "3790",
            "CSDVersionHex": "00000200",
            "CurrentVersion": "5.2",
            "ProductType": "WinNT",
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
            task_func=Runner.run_command, 
            config=config, 
            command=command, 
            arguments=arguments, 
            environment=environment
        )

    @staticmethod
    def run_executable(
        config: BottleConfig,
        file_path: str,
        arguments: str = "",
        environment: dict = False,
        no_async: bool = False,
        cwd: str = None,
        move_file: bool = False,
        move_progress: callable = None,
        terminal: bool = False
    ):
        '''
        Run an executable file with arguments and environment variables, inside
        a bottle using the config provided.
        '''
        logging.info("Running an executable on the bottle…")

        if file_path in [None, ""]:
            logging.error("No executable file path provided.")
            return False

        if move_file:
            new_path = ManagerUtils.move_file_to_bottle(
                file_path=file_path,
                config=config,
                fn_update=move_progress
            )
            if new_path:
                file_path = new_path

        command = f"'{file_path}'"

        if "msi" in file_path.split("."):
            command = f"msiexec /i '{file_path}'"
        elif "bat" in file_path.split("."):
            command = f"wineconsole cmd /c '{file_path}'"

        if no_async:
            Runner.run_command(
                config=config, 
                command=command,
                arguments=arguments, 
                environment=environment, 
                comunicate=True, 
                cwd=cwd,
                terminal=terminal
            )
            return Result(status=True)
        else:
            RunAsync(
                task_func=Runner.run_command, 
                config=config, 
                command=command, 
                arguments=arguments, 
                environment=environment,
                cwd=cwd,
                terminal=terminal
            )

    @staticmethod
    def run_winecfg(config: BottleConfig):
        logging.info("Running winecfg on the wineprefix…")
        RunAsync(
            task_func=Runner.run_command, 
            config=config, 
            command="winecfg"
        )

    @staticmethod
    def run_winetricks( config: BottleConfig):
        logging.info("Running winetricks on the wineprefix…")
        RunAsync(
            task_func=Runner.run_command, 
            config=config, 
            command="winetricks"
        )

    @staticmethod
    def run_debug(config: BottleConfig):
        logging.info("Running a debug console on the wineprefix…")
        RunAsync(
            task_func=Runner.run_command, 
            config=config, 
            command="winedbg",
            terminal=True,
            colors="debug"
        )

    @staticmethod
    def run_cmd(config: BottleConfig):
        logging.info("Running a CMD on the wineprefix…")
        RunAsync(
            task_func=Runner.run_command, 
            config=config, 
            command="cmd",
            terminal=True
        )

    @staticmethod
    def run_taskmanager(config: BottleConfig):
        logging.info("Running a Task manager on the wineprefix…")
        RunAsync(
            task_func=Runner.run_command, 
            config=config, 
            command="taskmgr"
        )

    @staticmethod
    def run_controlpanel( config: BottleConfig):
        logging.info("Running a Control panel on the wineprefix…")
        RunAsync(
            task_func=Runner.run_command, 
            config=config, 
            command="control"
        )

    @staticmethod
    def run_uninstaller(config: BottleConfig, uuid: str = False):
        logging.info("Running an Uninstaller on the wineprefix…")
        command = "uninstaller"

        if uuid:
            command = f"uninstaller --remove '{uuid}'"
            
        Runner.run_command(
            config=config, 
            command=command
        )

    @staticmethod
    def run_regedit(config: BottleConfig):
        logging.info("Running a Regedit on the wineprefix…")
        RunAsync(
            task_func=Runner.run_command, 
            config=config, 
            command="regedit"
        )

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
        cwd: str = None,
        colors: str = "default"
    ):
        '''
        Run a command inside a bottle using the config provided, supports
        the comunicate argument to wait for the command to finish and
        catch the output.
        '''
        path = ManagerUtils.get_bottle_path(config)
        runner = config.get("Runner")
        arch = config.get("Arch")
        gpu = GPUUtils().get_gpu()
        
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
            cwd = path

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
            runner = f"{runner}/files"
            if os.path.exists(f"{Paths.runners}/{runner}/dist"):
                runner = f"{runner}/dist"

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

        # Check for executable args from bottle config
        env = os.environ.copy()
        dll_overrides = []
        parameters = config["Parameters"]

        if config.get("DLL_Overrides"):
            for dll in config.get("DLL_Overrides").items():
                dll_overrides.append(f"{dll[0]}={dll[1]}")

        if config.get("Environment_Variables"):
            for env_var in config.get("Environment_Variables").items():
                env[env_var[0]] = env_var[1]

        if environment:
            if environment.get("WINEDLLOVERRIDES"):
                dll_overrides.append(environment["WINEDLLOVERRIDES"])
                del environment["WINEDLLOVERRIDES"]
            for e in environment:
                env[e] = environment[e]
        
        # hide mono and gecko to avoid popup dialogs
        dll_overrides.append("mscoree=d mshtml=d")

        if "FLATPAK_ID" in os.environ and parameters["use_runtime"] and not terminal:
            '''
            If the bottle is running inside a flatpak and the use_runtime
            parameter is set, add runtime libs to LD_LIBRARY_PATH.
            '''
            logging.info("Using runtime if available…")
            env["LD_LIBRARY_PATH"] = RuntimeManager.get_runtime_env()

            # ensure that runner libs can be found
            runner_path = ManagerUtils.get_runner_path(config.get("Runner"))
            runner_libs = []
            for lib in ["lib", "lib64"]:
                if os.path.exists(f"{runner_path}/{lib}"):
                    runner_libs.append(f"{runner_path}/{lib}")
            if runner_libs:
                if "LD_LIBRARY_PATH" in env:
                    env["LD_LIBRARY_PATH"] += ":".join(runner_libs)
                else:
                    env["LD_LIBRARY_PATH"] = ":".join(runner_libs)

        if parameters["dxvk"]:
            env["WINE_LARGE_ADDRESS_AWARE"] = "1"
            env["DXVK_STATE_CACHE_PATH"] = path
            env["STAGING_SHARED_MEMORY"] = "1"
            env["__GL_DXVK_OPTIMIZATIONS"] = "1"
            env["__GL_SHADER_DISK_CACHE"] = "1"
            env["__GL_SHADER_DISK_CACHE_PATH"] = path

        if parameters["dxvk_nvapi"]:
            dxvk_conf = f"{ManagerUtils.get_bottle_path(config)}/dxvk.conf"
            if not os.path.exists(dxvk_conf):
                # create dxvk.conf if it doesn't exist
                with open(dxvk_conf, "w") as f:
                    f.write("dxgi.nvapiHack = False")
            else:
                # check if dxvk.conf has the nvapiHack option, if not add it
                with open(dxvk_conf, "r") as f:
                    lines = f.readlines()
                with open(dxvk_conf, "w") as f:
                    for line in lines:
                        if "dxgi.nvapiHack" in line:
                            f.write("dxgi.nvapiHack = False\n")
                        else:
                            f.write(line)
            
            if "DXVK_CONFIG_FILE" not in config.get("Environment_Variables").keys():
                # add dxvk.conf to the environment variables if not
                env["DXVK_CONFIG_FILE"] = dxvk_conf
            
            if DisplayUtils.check_nvidia_device():
                # prevent wine from hiding the nvidia gpu
                env["WINE_HIDE_NVIDIA_GPU"] = "0"

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
            if not x_display:
                logging.error("Failed to get Xwayland display")
                return
            env["DISPLAY"] = x_display
            env["GDK_BACKEND"] = "x11"
            env["GDK_SDISPLAYALE"] = x_display

        if parameters["discrete_gpu"]:
            discrete = gpu["prime"]["discrete"]
            if discrete is not None:
                gpu_envs = discrete["envs"]
                for p in gpu_envs:
                    env[p] = gpu_envs[p]
                env["VK_ICD_FILENAMES"] = discrete["icd"]
        
        if "VK_ICD_FILENAMES" not in env.keys():
            if gpu["prime"]["integrated"] is not None:
                '''
                System support PRIME but user disabled the discrete GPU
                setting (previus check skipped), so using the integrated one.
                '''
                env["VK_ICD_FILENAMES"] = gpu["prime"]["integrated"]["icd"]
            else:
                '''
                System doesn't support PRIME, so using the first result
                from the gpu vendors list.
                '''
                _first = list(gpu["vendors"].keys())[0]
                env["VK_ICD_FILENAMES"] = gpu["vendors"][_first]["icd"]
                

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
            command = f"{gamemode_available} {command}"
        
        if terminal:
            return UtilsTerminal().execute(command, env, colors)
            
        if comunicate:
            try:
                res = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    shell=True,
                    env=env,
                    cwd=cwd
                ).communicate()[0]
            except:
                '''
                If return an exception, try to execute the command
                without the cwd argument
                '''
                res = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    shell=True,
                    env=env
                ).communicate()[0]

            enc = detect_encoding(res)
            if enc is not None:
                res = res.decode(enc)
            return res

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
            ).communicate()[0]

            enc = detect_encoding(res)
            if enc is not None:
                res = res.decode(enc)

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
            
        if version == "winxp" and config.get("Arch") == "win64":
            version = "winxp64"

        del_keys = {
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion": "SubVersionNumber",
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion": "VersionNumber",
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion": "CSDVersion",
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion": "CurrentBuildNumber",
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion": "CurrentVersion",
            "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\ProductOptions": "ProductType",
            "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\ServiceCurrent": "OS",
            "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\Windows": "CSDVersion",
            "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\ProductOptions": "ProductType",
            "HKEY_CURRENT_USER\\Softwarw\\Wine": "Version"
        }
        for d in del_keys:
            Runner.reg_delete(config, d, del_keys[d])
            
        Runner.reg_add(
            config=config,
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion",
            value="CSDVersion",
            data=Runner._windows_versions.get(version)["CSDVersion"]
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

        if "ProductType" in Runner._windows_versions.get(version):
            '''windows xp 32 doesn't have ProductOptions/ProductType key'''
            Runner.reg_add(
                config=config,
                key="HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\ProductOptions",
                value="ProductType",
                data=Runner._windows_versions.get(version)["ProductType"]
            )

        Runner.reg_add(
            config=config,
            key="HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\Windows",
            value="CSDVersion",
            data=Runner._windows_versions.get(version)["CSDVersionHex"],
            keyType="REG_DWORD"
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
            
        if version == "winxp" and config.get("Arch") == "win64":
            version = "winxp64"
            
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
        )

        if winedbg in [None, ""]:
            return processes
        
        winedbg = winedbg.split("\n")

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
    def wait_for_process(config:BottleConfig, name:str, timeout:int = 1):
        '''
        Wait for a process to exit.
        '''
        while True:
            processes = Runner.get_processes(config)
            if len(processes) == 0:
                break
            if name not in [p["name"] for p in processes]:
                break
            time.sleep(timeout)
        return True
    
    @staticmethod
    def kill_process(config:BottleConfig, pid:str=None, name:str=None):
        '''
        Kill a process by its PID or name.
        '''
        if pid:
            command = "\n".join([
                "winedbg << END_OF_INPUTS",
                f"attach 0x{pid}",
                "kill",
                "quit",
                "END_OF_INPUTS"
            ])
            res = Runner.run_command(
                config,
                command=command,
                comunicate=True
            )
            if "error 5" in res and name:
                res = subprocess.Popen(
                    f"kill $(pgrep {name[:15]})",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True
                )
                return res
            return Runner.wineboot(config, status=0)
        elif name:
            processes = Runner.get_processes(config)
            for p in processes:
                if p["name"] == name:
                    Runner.kill_process(config, p["pid"], name)
    
    @staticmethod
    def is_process_alive(config:BottleConfig, pid:str=None, name:str=None):
        '''
        Check if a process is running on the wineprefix.
        '''
        processes = Runner.get_processes(config)
        if pid:
            return pid in [p["pid"] for p in processes]
        elif name:
            return name in [p["name"] for p in processes]
        return False

    @staticmethod
    def apply_cmd_settings(config:BottleConfig, scheme:dict={}):
        '''
        Change settings for the wine command line in a bottle.
        This method can also be used to apply the default settings, part
        of the Bottles experience, these are meant to improve the
        readability and usability.
        '''
        for key, value in CMDSettings.items():
            if key not in scheme:
                scheme[key] = value

        for key, value in scheme.items():
            keyType="REG_DWORD"

            if key == "FaceName":
                keyType="REG_SZ"

            Runner.reg_add(
                config,
                key="HKEY_CURRENT_USER\\Console\\C:_windows_system32_wineconsole.exe",
                value=key,
                data=value,
                keyType=keyType
            )
        
