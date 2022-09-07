import os
import shutil
import subprocess
from typing import NewType

from bottles.backend.utils.generic import detect_encoding  # pyright: reportMissingImports=false
from bottles.backend.managers.runtime import RuntimeManager
from bottles.backend.managers.sandbox import SandboxManager
from bottles.backend.utils.terminal import TerminalUtils
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.display import DisplayUtils
from bottles.backend.utils.gpu import GPUUtils
from bottles.backend.globals import Paths, gamemode_available, gamescope_available, mangohud_available, \
    obs_vkc_available, vkbasalt_available, vmtouch_available
from bottles.backend.logger import Logger
from bottles.frontend.utils.threading import RunAsync

logging = Logger()


class WineEnv:
    """
    This class is used to store and return a command environment.
    """
    __env: dict = {}
    __result: dict = {
        "envs": {},
        "overrides": []
    }

    def __init__(self, clean: bool = False):
        self.__env = {}
        if not clean:
            self.__env = os.environ.copy()

    def add(self, key, value, override=False):
        if key in self.__env:
            if override:
                self.__result["overrides"].append(f"{key}={value}")
            else:
                return
        self.__env[key] = value

    def add_bundle(self, bundle, override=False):
        for key, value in bundle.items():
            self.add(key, value, override)

    def get(self):
        result = self.__result
        result["count_envs"] = len(result["envs"])
        result["count_overrides"] = len(result["overrides"])
        result["envs"] = self.__env
        return result

    def remove(self, key):
        if key in self.__env:
            del self.__env[key]

    def is_empty(self, key):
        return len(self.__env.get(key, "").strip()) == 0

    def concat(self, key, values, sep=":"):
        if isinstance(values, str):
            values = [values]
        values = sep.join(values)

        if self.has(key):
            values = self.__env[key] + sep + values
        self.add(key, values, True)

    def has(self, key):
        return key in self.__env


class WineCommand:
    """
    This class is used to run a wine command with a custom environment.
    It also handles the launch in a terminal or not.
    """

    def __init__(
            self,
            config: dict,
            command: str,
            terminal: bool = False,
            arguments: str = False,
            environment: dict = False,
            communicate: bool = False,
            cwd: str = None,
            colors: str = "default",
            minimal: bool = False,  # avoid gamemode/gamescope usage
            post_script: str = None
    ):
        self.config = config
        self.minimal = minimal
        self.arguments = arguments
        self.cwd = self.__get_cwd(cwd)
        self.runner = self.__get_runner()
        self.command = self.get_cmd(command, post_script)
        self.terminal = terminal
        self.env = self.get_env(environment)
        self.communicate = communicate
        self.colors = colors
        self.vmtouch_files = None

    def __get_cwd(self, cwd) -> str:
        config = self.config

        if config.get("Environment", "Custom") == "Steam":
            bottle = config.get("Path")
        else:
            bottle = ManagerUtils.get_bottle_path(config)

        if not cwd:
            '''
            If no cwd is given, use the WorkingDir from the
            bottle configuration.
            '''
            cwd = config.get("WorkingDir")
        if cwd == "" or not os.path.exists(cwd):
            '''
            If the WorkingDir is empty, use the bottle path as
            working directory.
            '''
            cwd = bottle

        return cwd

    def get_env(self, environment: dict = None, return_steam_env: bool = False, return_clean_env: bool = False) -> dict:
        env = WineEnv(clean=return_steam_env or return_clean_env)
        config = self.config
        arch = config.get("Arch", None)
        params = config.get("Parameters", None)

        if None in [arch, params]:
            return env.get()["envs"]

        if environment is None:
            environment = {}

        if config.get("Environment", "Custom") == "Steam":
            bottle = config.get("Path")
        else:
            bottle = ManagerUtils.get_bottle_path(config)

        dll_overrides = []
        gpu = GPUUtils().get_gpu()
        is_nvidia = DisplayUtils.check_nvidia_device()
        ld = []

        # Bottle environment variables
        if config.get("Environment_Variables"):
            for var in config.get("Environment_Variables").items():
                env.add(var[0], var[1], override=True)

        # Environment variables from argument
        if environment:
            if environment.get("WINEDLLOVERRIDES"):
                dll_overrides.append(environment["WINEDLLOVERRIDES"])
                del environment["WINEDLLOVERRIDES"]

            if environment.get("DXVK_CONFIG_FILE", "") == "bottle_root":
                environment["DXVK_CONFIG_FILE"] = os.path.join(bottle, "dxvk.conf")

            for e in environment:
                env.add(e, environment[e], override=True)

        # Language
        if config["Language"] != "sys":
            env.add("LC_ALL", config["Language"])

        # Bottle DLL_Overrides
        if config["DLL_Overrides"]:
            for dll in config.get("DLL_Overrides").items():
                dll_overrides.append(f"{dll[0]}={dll[1]}")

        # Default DLL overrides
        if not return_steam_env:
            dll_overrides.append("mshtml=d")
            dll_overrides.append("winemenubuilder=''")

        # Get Runtime libraries
        if (params.get("use_runtime") or params.get("use_eac_runtime") or params.get("use_be_runtime")) \
                and not self.terminal and not return_steam_env:
            _rb = RuntimeManager.get_runtime_env("bottles")
            if _rb:
                _eac = RuntimeManager.get_eac()
                _be = RuntimeManager.get_be()

                if params.get("use_runtime"):
                    logging.info("Using Bottles runtime")
                    ld += _rb

                if _eac and not self.minimal:  # NOTE: should check for runner compatibility with "eac" (?)
                    logging.info("Using EasyAntiCheat runtime")
                    env.add("PROTON_EAC_RUNTIME", _eac)
                    dll_overrides.append("easyanticheat_x86,easyanticheat_x64=b,n")

                if _be and not self.minimal:  # NOTE: should check for runner compatibility with "be" (?)
                    logging.info("Using BattlEye runtime")
                    env.add("PROTON_BATTLEYE_RUNTIME", _be)
                    dll_overrides.append("beclient,beclient_x64=b,n")
            else:
                logging.warning("Bottles runtime was requested but not found")

        # Get Runner libraries
        runner_path = ManagerUtils.get_runner_path(config.get("Runner"))
        if arch == "win64":
            runner_libs = [
                "lib/wine/x86_64-unix",
                "lib32/wine/x86_64-unix",
                "lib64/wine/x86_64-unix",
                "lib/wine/i386-unix",
                "lib32/wine/i386-unix",
                "lib64/wine/i386-unix"
            ]
        else:
            runner_libs = [
                "lib/wine/i386-unix",
                "lib32/wine/i386-unix",
                "lib64/wine/i386-unix"
            ]
        for lib in runner_libs:
            _path = os.path.join(runner_path, lib)
            if os.path.exists(_path):
                ld.append(_path)

        # DXVK environment variables
        if params["dxvk"] and not return_steam_env:
            env.add("WINE_LARGE_ADDRESS_AWARE", "1")
            env.add("DXVK_STATE_CACHE_PATH", os.path.join(bottle, "cache", "dxvk_state"))
            env.add("STAGING_SHARED_MEMORY", "1")
            env.add("__GL_DXVK_OPTIMIZATIONS", "1")
            env.add("__GL_SHADER_DISK_CACHE", "1")
            env.add("__GL_SHADER_DISK_CACHE_SKIP_CLEANUP", "1")  # should not be needed anymore
            env.add("__GL_SHADER_DISK_CACHE_PATH", os.path.join(bottle, "cache", "gl_shader"))
            env.add("MESA_SHADER_CACHE_DIR", os.path.join(bottle, "cache", "mesa_shader"))

        # VKD£D environment variables
        if params["vkd3d"] and not return_steam_env:
            env.add("VKD3D_SHADER_CACHE_PATH", os.path.join(bottle, "cache", "vkd3d_shader"))

        # LatencyFleX environment variables
        if params["latencyflex"] and not return_steam_env:
            _lf_path = ManagerUtils.get_latencyflex_path(config.get("LatencyFleX"))
            _lf_icd = os.path.join(_lf_path, "layer/usr/share/vulkan/implicit_layer.d/latencyflex.json")
            env.concat("VK_ICD_FILENAMES", _lf_icd)

        # Mangohud environment variables
        if params["mangohud"] and not self.minimal and not (gamescope_available and params.get("gamescope")):
            env.add("MANGOHUD", "1")
            env.add("MANGOHUD_DLSYM", "1")

        # vkBasalt environment variables
        if params["vkbasalt"] and not self.minimal:
            vkbasalt_conf_path = os.path.join(ManagerUtils.get_bottle_path(config), "vkBasalt.conf")
            if os.path.isfile(vkbasalt_conf_path):
                env.add("VKBASALT_CONFIG_FILE", vkbasalt_conf_path)
            env.add("ENABLE_VKBASALT", "1")

        # OBS Vulkan Capture environment variables
        if params["obsvkc"] and not self.minimal:
            env.add("OBS_VKCAPTURE", "1")
            if DisplayUtils.display_server_type() == "x11":
                env.add("OBS_USE_EGL", "1")

        # DXVK-Nvapi environment variables
        if params["dxvk_nvapi"] and not return_steam_env:
            conf = self.__set_dxvk_nvapi_conf(bottle)
            env.add("DXVK_CONFIG_FILE", conf)
            # NOTE: users reported that DXVK_ENABLE_NVAPI and DXVK_NVAPIHACK must be set to make
            #       DLSS works. I don't have a GPU compatible with this tech, so I'll trust them
            env.add("DXVK_NVAPIHACK", "0")
            env.add("DXVK_ENABLE_NVAPI", "1")

            # Prevent wine from hiding the Nvidia GPU with DXVK-Nvapi enabled
            if is_nvidia:
                env.add("WINE_HIDE_NVIDIA_GPU", "1")

        # Esync environment variable
        if params["sync"] == "esync":
            env.add("WINEESYNC", "1")

        # Fsync environment variable
        if params["sync"] == "fsync":
            env.add("WINEFSYNC", "1")

        # Futex2 environment variable
        if params["sync"] == "futex2":
            env.add("WINEFSYNC_FUTEX2", "1")

        # Wine debug level
        if not return_steam_env:
            debug_level = "fixme-all"
            if params["fixme_logs"]:
                debug_level = "+fixme-all"
            env.add("WINEDEBUG", debug_level)

        # LatencyFleX
        if params["latencyflex"] and params["dxvk_nvapi"] and not return_steam_env:
            _lf_path = ManagerUtils.get_latencyflex_path(config["LatencyFleX"])
            ld.append(os.path.join(_lf_path, "wine/usr/lib/wine/x86_64-unix"))

        # Aco compiler
        # if params["aco_compiler"]:
        #     env.add("ACO_COMPILER", "aco")

        # FSR
        if params["fsr"]:
            env.add("WINE_FULLSCREEN_FSR", "1")
            env.add("WINE_FULLSCREEN_FSR_STRENGTH", str(params["fsr_level"]))

        # PulseAudio latency
        if params["pulseaudio_latency"]:
            env.add("PULSE_LATENCY_MSEC", "60")

        # Discrete GPU
        if not return_steam_env:
            if params["discrete_gpu"]:
                discrete = gpu["prime"]["discrete"]
                if discrete is not None:
                    gpu_envs = discrete["envs"]
                    for p in gpu_envs:
                        env.add(p, gpu_envs[p])
                    env.add("VK_ICD_FILENAMES", discrete["icd"])

            # VK_ICD
            if not env.has("VK_ICD_FILENAMES"):
                if gpu["prime"]["integrated"] is not None:
                    '''
                    System support PRIME but user disabled the discrete GPU
                    setting (previus check skipped), so using the integrated one.
                    '''
                    env.add("VK_ICD_FILENAMES", gpu["prime"]["integrated"]["icd"])
                else:
                    '''
                    System doesn't support PRIME, so using the first result
                    from the gpu vendors list.
                    '''
                    if "vendors" in gpu and len(gpu["vendors"]) > 0:
                        _first = list(gpu["vendors"].keys())[0]
                        env.add("VK_ICD_FILENAMES", gpu["vendors"][_first]["icd"])
                    else:
                        logging.warning("No GPU vendor found, keep going without setting VK_ICD_FILENAMES…")

            # Add ld to LD_LIBRARY_PATH
            if ld:
                env.concat("LD_LIBRARY_PATH", ld)

        # Vblank
        # env.add("__GL_SYNC_TO_VBLANK", "0")
        # env.add("vblank_mode", "0")

        # DLL Overrides
        env.concat("WINEDLLOVERRIDES", dll_overrides, sep=";")
        if env.is_empty("WINEDLLOVERRIDES"):
            env.remove("WINEDLLOVERRIDES")

        if not return_steam_env:
            # Wine prefix
            env.add("WINEPREFIX", bottle, override=True)
            # Wine arch
            env.add("WINEARCH", arch)

        return env.get()["envs"]

    def __get_runner(self) -> str:
        config = self.config
        runner = config.get("Runner")
        arch = config.get("Arch")

        if config.get("Environment", "Custom") == "Steam":
            runner = config.get("RunnerPath", None)

        if runner in [None, ""]:
            return ""

        if "Proton" in runner \
                and "lutris" not in runner \
                and config.get("Environment", "") != "Steam":
            '''
            If the runner is Proton, set the pat to /dist or /files 
            based on check if files exists.
            '''
            _runner = f"{runner}/files"
            if os.path.exists(f"{Paths.runners}/{runner}/dist"):
                _runner = f"{runner}/dist"
            runner = f"{Paths.runners}/{_runner}/bin/wine"

        elif config.get("Environment", "") == "Steam":
            '''
            If the environment is Steam, runner path is defined
            in the bottle configuration and point to the right
            main folder.
            '''
            runner = f"{runner}/bin/wine"

        elif runner.startswith("sys-"):
            '''
            If the runner type is system, set the runner binary
            path to the system command. Else set it to the full path.
            '''
            runner = shutil.which("wine")

        else:
            runner = f"{Paths.runners}/{runner}/bin/wine"

        if arch == "win64":
            runner = f"{runner}64"

        runner = runner.replace(" ", "\\ ")

        return runner

    def get_cmd(self, command, post_script: str = None, return_steam_cmd: bool = False, return_clean_cmd: bool = False) -> str:
        config = self.config
        params = config.get("Parameters", {})
        runner = self.runner

        if return_clean_cmd:
            return_steam_cmd = True

        if not return_steam_cmd and not return_clean_cmd:
            command = f"{runner} {command}"

        if not self.minimal:
            if gamemode_available and params.get("gamemode"):
                if not return_steam_cmd:
                    command = f"{gamemode_available} {command}"
                else:
                    command = f"gamemode {command}"

            if mangohud_available and params.get("mangohud"):
                if not return_steam_cmd:
                    command = f"{mangohud_available} {command}"
                else:
                    command = f"mangohud {command}"

            if gamescope_available and params.get("gamescope"):
                command = f"{self.__get_gamescope_cmd(return_steam_cmd)}  -- {command}"

            if obs_vkc_available and params.get("obsvkc"):
                command = f"{obs_vkc_available} {command}"

        if params.get("use_steam_runtime"):
            _rs = RuntimeManager.get_runtimes("steam")
            _picked = {}

            if _rs:
                if "soldier" in _rs.keys() and "proton" in self.runner.lower():
                    ''' 
                    Soldier doesn't works with Soda/Caffe and maybe other Wine runners, but it
                    works with Proton. So, if the runner is Proton, use the soldier runtime.
                    '''
                    _picked = _rs["soldier"]
                elif "scout" in _rs.keys():
                    _picked = _rs["scout"]
            else:
                logging.warning("Steam runtime was requested but not found")

            if _picked:
                logging.info(f"Using Steam runtime {_picked['name']}")
                command = f"{_picked['entry_point']} {command}"
            else:
                logging.warning("Steam runtime was requested and found but there are no valid combinations")

        if self.arguments:
            if "%command%" in self.arguments:
                prefix = self.arguments.split("%command%")[0]
                suffix = self.arguments.split("%command%")[1]
                command = f"{prefix} {command} {suffix}"
            else:
                command = f"{command} {self.arguments}"

        if post_script is not None:
            command = f"{command} ; sh '{post_script}'"

        return command

    def __get_gamescope_cmd(self, return_steam_cmd: bool = False) -> str:
        config = self.config
        params = config["Parameters"]
        gamescope_cmd = []

        if gamescope_available and params["gamescope"]:
            gamescope_cmd = [gamescope_available]
            if return_steam_cmd:
                gamescope_cmd = ["gamescope"]
            if params["gamescope_fullscreen"]:
                gamescope_cmd.append("-f")
            if params["gamescope_borderless"]:
                gamescope_cmd.append("-b")
            if params["gamescope_scaling"]:
                gamescope_cmd.append("-n")
            if params["fsr"]:
                gamescope_cmd.append("-U")
            if params["gamescope_fps"] > 0:
                gamescope_cmd.append(f"-r {params['gamescope_fps']}")
            if params["gamescope_fps_no_focus"] > 0:
                gamescope_cmd.append(f"-o {params['gamescope_fps_no_focus']}")
            if params["gamescope_game_width"] > 0:
                gamescope_cmd.append(f"-w {params['gamescope_game_width']}")
            if params["gamescope_game_height"] > 0:
                gamescope_cmd.append(f"-h {params['gamescope_game_height']}")
            if params["gamescope_window_width"] > 0:
                gamescope_cmd.append(f"-W {params['gamescope_window_width']}")
            if params["gamescope_window_height"] > 0:
                gamescope_cmd.append(f"-H {params['gamescope_window_height']}")

        return " ".join(gamescope_cmd)

    def vmtouch_preload(self):
        vmtouch_flags = "-t -v -l -d"
        vmtouch_file_size = " -m 1024M"
        if self.command.find("C:\\") > 0:
            self.vmtouch_files = "'"+(self.cwd+"/"+(self.command.split(" ")[-1].split('\\')[-1])).replace('\'', "")+"'"
        else:
            self.vmtouch_files = "'"+self.command.split(" ")[-1]+"'"

        #if self.config["Parameters"].get("vmtouch_cache_cwd"):
        #    self.vmtouch_files = "'"+self.vmtouch_files+"' '"+self.cwd+"/'" Commented out as fix for #1941
        self.command = vmtouch_available+" "+vmtouch_flags+" "+vmtouch_file_size+" "+self.vmtouch_files+" && "+self.command

    def vmtouch_free(self):
        subprocess.Popen(
            "kill $(pidof vmtouch)",
            shell=True,
            env=self.env,
            cwd=self.cwd,
        )
        if not self.vmtouch_files:
            return

        vmtouch_flags = "-e -v"
        command = vmtouch_available+" "+vmtouch_flags+" "+self.vmtouch_files
        subprocess.Popen(
            command,
            shell=True,
            env=self.env,
            cwd=self.cwd,
        )

    def run(self):
        if None in [self.runner, self.env]:
            return

        if vmtouch_available and self.config["Parameters"].get("vmtouch"):
            self.vmtouch_preload()

        if self.config["Parameters"].get("sandbox"):
            permissions = self.config["Sandbox"]
            sandbox = SandboxManager(
                envs=self.env,
                chdir=self.cwd,
                share_paths_rw=[ManagerUtils.get_bottle_path(self.config)],
                share_paths_ro=[
                    Paths.runners,
                    Paths.temp
                ],
                share_net=permissions.get("share_net", False),
                share_sound=permissions.get("share_sound", False),
            )
            if self.terminal:
                return TerminalUtils().execute(sandbox.get_cmd(self.command), self.env, self.colors)

            proc = sandbox.run(self.command)

        else:
            if self.terminal:
                return TerminalUtils().execute(self.command, self.env, self.colors)

            try:
                proc = subprocess.Popen(
                    self.command,
                    stdout=subprocess.PIPE,
                    shell=True,
                    env=self.env,
                    cwd=self.cwd
                )
                proc.wait()
            except FileNotFoundError:
                return
                
        res = proc.communicate()[0]
        enc = detect_encoding(res)

        if vmtouch_available and self.config["Parameters"].get("vmtouch"):
            self.vmtouch_free()

        if enc is not None:
            res = res.decode(enc)

        if self.communicate:
            return res

        try:
            '''
            Read the output to catch the wine ShellExecuteEx exception, so we can 
            raise it as a python exception and handle it in other parts of the code.
            '''
            if "ShellExecuteEx" in res:
                raise ValueError("ShellExecuteEx")
        except ValueError:
            '''
            Try running the command without some args which can cause the exception.
            '''
            res = subprocess.Popen(self.command, shell=True, env=self.env)
            if self.communicate:
                return res.communicate()
            return res

    @staticmethod
    def __set_dxvk_nvapi_conf(bottle: str):
        """
        TODO: This should be moved to a dedicated DXVKConf class when
              we will provide a way to set the DXVK configuration.
        """
        dxvk_conf = f"{bottle}/dxvk.conf"
        if not os.path.exists(dxvk_conf):
            # create dxvk.conf if doesn't exist
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

        return dxvk_conf
