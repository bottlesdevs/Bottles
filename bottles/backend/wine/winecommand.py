import os
import shutil
import stat
import subprocess
import tempfile
import shlex

from bottles.backend.globals import (
    Paths,
    gamemode_available,
    gamescope_available,
    mangohud_available,
    obs_vkc_available,
    vmtouch_available,
)
import logging
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.display import DisplayUtils
from bottles.backend.utils.generic import detect_encoding
from bottles.backend.utils.gpu import GPUUtils
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.terminal import TerminalUtils


class WineEnv:
    """
    This class is used to store and return a command environment.
    """

    __env: dict = {}
    __result: dict = {"envs": {}, "overrides": []}

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
        config: BottleConfig,
        command: str,
        terminal: bool = False,
        arguments: str = "",
        environment: dict = {},
        communicate: bool = False,
        colors: str = "default",
        minimal: bool = False,  # avoid gamemode/gamescope usage
        pre_script: str | None = None,
        post_script: str | None = None,
        cwd: str | None = None,
        midi_soundfont: str | None = None,
    ):
        _environment = environment.copy()
        self.config = self._get_config(config)
        self.minimal = minimal
        self.arguments = arguments
        self.cwd = self._get_cwd(cwd)
        self.runner, self.runner_runtime = self._get_runner_info()
        self.gamescope_activated = (
            environment["GAMESCOPE"] == "1"
            if "GAMESCOPE" in environment
            else self.config.Parameters.gamescope
        )
        self.command = self.get_cmd(
            command, pre_script, post_script, midi_soundfont, environment=_environment
        )
        self.terminal = terminal
        self.env = self.get_env(_environment)
        self.communicate = communicate
        self.colors = colors
        self.vmtouch_files = None

    def _get_config(self, config: BottleConfig) -> BottleConfig:
        if cnf := config.data.get("config"):
            return cnf

        if not isinstance(config, BottleConfig):
            logging.error("Invalid config type: %s" % type(config))
            return BottleConfig()

        return config

    def _get_cwd(self, cwd) -> str:
        config = self.config

        bottle = ManagerUtils.get_bottle_path(config)

        if not cwd:
            """
            If no cwd is given, use the WorkingDir from the
            bottle configuration.
            """
            cwd = config.WorkingDir
        if cwd == "" or not os.path.exists(cwd):
            """
            If the WorkingDir is empty, use the bottle path as
            working directory.
            """
            cwd = bottle

        return cwd

    def get_env(
        self,
        environment: dict | None = None,
    ) -> dict:
        env = WineEnv()
        config = self.config
        arch = config.Arch
        params = config.Parameters

        # Bottle Path as environment variable
        env.add("BOTTLE", config.Path)

        if None in [arch, params]:
            return env.get()["envs"]

        if environment is None:
            environment = {}

        bottle = ManagerUtils.get_bottle_path(config)
        runner_path = ManagerUtils.get_runner_path(config.Runner)

        # Clean some env variables which can cause trouble
        # ref: <https://github.com/bottlesdevs/Bottles/issues/2127>
        # env.remove("XDG_DATA_HOME")

        dll_overrides = []
        gpu = GPUUtils().get_gpu()
        DisplayUtils.check_nvidia_device()
        ld = []

        # Bottle environment variables
        if config.Environment_Variables:
            for key, value in config.Environment_Variables.items():
                env.add(key, value, override=True)

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
        if config.Language != "sys":
            env.add("LC_ALL", config.Language)

        # Bottle DLL_Overrides
        if config.DLL_Overrides:
            for k, v in config.DLL_Overrides.items():
                dll_overrides.append(f"{k}={v}")

        # Default DLL overrides
        dll_overrides.append("winemenubuilder=''")

        # Get Runner libraries
        if arch == "win64":
            runner_libs = [
                "lib",
                "lib64",
                "lib/wine/x86_64-unix",
                "lib32/wine/x86_64-unix",
                "lib64/wine/x86_64-unix",
                "lib/wine/i386-unix",
                "lib32/wine/i386-unix",
                "lib64/wine/i386-unix",
            ]
            gst_libs = [
                "lib64/gstreamer-1.0",
                "lib/gstreamer-1.0",
                "lib32/gstreamer-1.0",
            ]
        else:
            runner_libs = [
                "lib",
                "lib/wine/i386-unix",
                "lib32/wine/i386-unix",
                "lib64/wine/i386-unix",
            ]
            gst_libs = ["lib/gstreamer-1.0", "lib32/gstreamer-1.0"]

        for lib in runner_libs:
            _path = os.path.join(runner_path, lib)
            if os.path.exists(_path):
                ld.append(_path)

        # Embedded GStreamer environment variables
        if not env.has("BOTTLES_USE_SYSTEM_GSTREAMER"):
            gst_env_path = []
            for lib in gst_libs:
                if os.path.exists(os.path.join(runner_path, lib)):
                    gst_env_path.append(os.path.join(runner_path, lib))
            if len(gst_env_path) > 0:
                env.add("GST_PLUGIN_SYSTEM_PATH", ":".join(gst_env_path), override=True)

        # DXVK environment variables
        if params.dxvk:
            env.add("WINE_LARGE_ADDRESS_AWARE", "1")
            env.add(
                "DXVK_STATE_CACHE_PATH", os.path.join(bottle, "cache", "dxvk_state")
            )
            env.add("STAGING_SHARED_MEMORY", "1")
            env.add("__GL_SHADER_DISK_CACHE", "1")
            env.add(
                "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP", "1"
            )  # should not be needed anymore
            env.add(
                "__GL_SHADER_DISK_CACHE_PATH",
                os.path.join(bottle, "cache", "gl_shader"),
            )
            env.add(
                "MESA_SHADER_CACHE_DIR", os.path.join(bottle, "cache", "mesa_shader")
            )

        # VKD3D environment variables
        if params.vkd3d:
            env.add(
                "VKD3D_SHADER_CACHE_PATH", os.path.join(bottle, "cache", "vkd3d_shader")
            )

        # LatencyFleX environment variables
        if params.latencyflex:
            _lf_path = ManagerUtils.get_latencyflex_path(config.LatencyFleX)
            _lf_layer_path = os.path.join(
                _lf_path, "layer/usr/share/vulkan/implicit_layer.d"
            )
            env.concat("VK_ADD_LAYER_PATH", _lf_layer_path)
            env.add("LFX", "1")
            ld.append(os.path.join(_lf_path, "layer/usr/lib/x86_64-linux-gnu"))
        else:
            env.add("DISABLE_LFX", "1")

        # Mangohud environment variables
        if (
            params.mangohud
            and not self.minimal
            and not (gamescope_available and self.gamescope_activated)
        ):
            env.add("MANGOHUD", "1")
            env.add("MANGOHUD_DLSYM", "1")
            if not params.mangohud_display_on_game_start:
                env.add("MANGOHUD_CONFIG", "no_display")

        # vkBasalt environment variables
        if params.vkbasalt and not self.minimal:
            vkbasalt_conf_path = os.path.join(
                ManagerUtils.get_bottle_path(config), "vkBasalt.conf"
            )
            if os.path.isfile(vkbasalt_conf_path):
                env.add("VKBASALT_CONFIG_FILE", vkbasalt_conf_path)
            env.add("ENABLE_VKBASALT", "1")

        # OBS Vulkan Capture environment variables
        if params.obsvkc and not self.minimal:
            env.add("OBS_VKCAPTURE", "1")
            if DisplayUtils.display_server_type() == "x11":
                env.add("OBS_USE_EGL", "1")

        # DXVK-Nvapi environment variables
        if params.dxvk_nvapi:
            # NOTE: users reported that DXVK_ENABLE_NVAPI and DXVK_NVAPIHACK must be set to make
            #       DLSS works. I don't have a GPU compatible with this tech, so I'll trust them
            env.add("DXVK_NVAPIHACK", "0")
            env.add("DXVK_ENABLE_NVAPI", "1")

        # Esync environment variable
        if params.sync == "esync":
            env.add("WINEESYNC", "1")

        # Fsync environment variable
        if params.sync == "fsync":
            env.add("WINEFSYNC", "1")

        # Wine debug level
        debug_level = "fixme-all"
        if params.fixme_logs:
            debug_level = "+fixme-all"
        env.add("WINEDEBUG", debug_level)

        # Aco compiler
        # if params["aco_compiler"]:
        #     env.add("ACO_COMPILER", "aco")

        # FSR
        if params.fsr:
            env.add("WINE_FULLSCREEN_FSR", "1")
            env.add("WINE_FULLSCREEN_FSR_STRENGTH", str(params.fsr_sharpening_strength))
            if params.fsr_quality_mode:
                env.add("WINE_FULLSCREEN_FSR_MODE", str(params.fsr_quality_mode))

        # PulseAudio latency
        if params.pulseaudio_latency:
            env.add("PULSE_LATENCY_MSEC", "60")

        # Discrete GPU
        if params.discrete_gpu:
            discrete = gpu["prime"]["discrete"]
            if discrete is not None:
                gpu_envs = discrete["envs"]
                for p in gpu_envs:
                    env.add(p, gpu_envs[p])
                env.concat("VK_ICD_FILENAMES", discrete["icd"])

        # VK_ICD
        if not env.has("VK_ICD_FILENAMES"):
            if gpu["prime"]["integrated"] is not None:
                """
                System support PRIME but user disabled the discrete GPU
                setting (previus check skipped), so using the integrated one.
                """
                env.concat("VK_ICD_FILENAMES", gpu["prime"]["integrated"]["icd"])
            else:
                """
                System doesn't support PRIME, so using the first result
                from the gpu vendors list.
                """
                if "vendors" in gpu and len(gpu["vendors"]) > 0:
                    _first = list(gpu["vendors"].keys())[0]
                    env.concat("VK_ICD_FILENAMES", gpu["vendors"][_first]["icd"])
                else:
                    logging.warning(
                        "No GPU vendor found, keep going without setting VK_ICD_FILENAMES…"
                    )

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

        # Wine prefix
        env.add("WINEPREFIX", bottle, override=True)
        # Wine arch
        env.add("WINEARCH", arch)

        return env.get()["envs"]

    def _get_runner_info(self) -> tuple[str, str]:
        config = self.config
        runner = ManagerUtils.get_runner_path(config.Runner)
        arch = config.Arch
        runner_runtime = ""

        if runner in [None, ""]:
            return "", ""

        if runner.startswith("sys-"):
            """
            If the runner type is system, set the runner binary
            path to the system command. Else set it to the full path.
            """
            runner = shutil.which("wine")

        else:
            runner = f"{runner}/bin/wine"

        if arch == "win64":
            runner = f"{runner}64"

        runner = shlex.quote(runner)  # type: ignore

        return runner, runner_runtime

    def get_cmd(
        self,
        command,
        pre_script: str | None = None,
        post_script: str | None = None,
        midi_soundfont: str | None = None,
        environment: dict | None = None,
    ) -> str:
        config = self.config
        params = config.Parameters
        runner = self.runner

        if environment is None:
            environment = {}

        command = f"{runner} {command}"

        if not self.minimal:
            if gamemode_available and params.gamemode:
                command = f"{gamemode_available} {command}"

            if mangohud_available and params.mangohud and not self.gamescope_activated:
                command = f"{mangohud_available} {command}"

            if gamescope_available and self.gamescope_activated:
                gamescope_run = tempfile.NamedTemporaryFile(mode="w", suffix=".sh").name

                # Create temporary sh script in /tmp where Gamescope will execute it
                file = ["#!/usr/bin/env sh\n"]
                file.append(f"{command} $@")
                if mangohud_available and params.mangohud:
                    file.append(" &\nmangoapp")
                with open(gamescope_run, "w") as f:
                    f.write("".join(file))

                # Update command
                command = f"{self._get_gamescope_cmd()} -- {gamescope_run}"
                logging.info(f"Running Gamescope command: '{command}'")
                logging.info(f"{gamescope_run} contains:")
                with open(gamescope_run) as f:
                    logging.info(f"\n\n{f.read()}")

                # Set file as executable
                st = os.stat(gamescope_run)
                os.chmod(gamescope_run, st.st_mode | stat.S_IEXEC)

            if obs_vkc_available and params.obsvkc:
                command = f"{obs_vkc_available} {command}"

        if post_script not in (None, ""):
            command = f"{command} ; sh '{post_script}'"

        if pre_script not in (None, ""):
            command = f"sh '{pre_script}' ; {command}"

        return command

    def _get_gamescope_cmd(self) -> str:
        config = self.config
        params = config.Parameters
        gamescope_cmd = []

        if gamescope_available and self.gamescope_activated:
            gamescope_cmd = [gamescope_available]
            if params.gamescope_fullscreen:
                gamescope_cmd.append("-f")
            if params.gamescope_borderless:
                gamescope_cmd.append("-b")
            if params.gamescope_scaling:
                gamescope_cmd.append("-S integer")
            if params.fsr:
                gamescope_cmd.append("-F fsr")
                # Upscaling sharpness is from 0 to 20. There are 5 FSR upscaling levels,
                # so multiply by 4 to reach 20
                gamescope_cmd.append(
                    f"--fsr-sharpness {params.fsr_sharpening_strength * 4}"
                )
            if params.gamescope_fps > 0:
                gamescope_cmd.append(f"-r {params.gamescope_fps}")
            if params.gamescope_fps_no_focus > 0:
                gamescope_cmd.append(f"-o {params.gamescope_fps_no_focus}")
            if params.gamescope_game_width > 0:
                gamescope_cmd.append(f"-w {params.gamescope_game_width}")
            if params.gamescope_game_height > 0:
                gamescope_cmd.append(f"-h {params.gamescope_game_height}")
            if params.gamescope_window_width > 0:
                gamescope_cmd.append(f"-W {params.gamescope_window_width}")
            if params.gamescope_window_height > 0:
                gamescope_cmd.append(f"-H {params.gamescope_window_height}")

        return " ".join(gamescope_cmd)

    def _vmtouch_preload(self):
        vmtouch_flags = "-t -v -l -d"
        vmtouch_file_size = " -m 1024M"
        if self.command.find("C:\\") > 0:
            s = (
                self.cwd + "/" + (self.command.split(" ")[-1].split("\\")[-1])
            ).replace("'", "")
        else:
            s = self.command.split(" ")[-1]
        self.vmtouch_files = shlex.quote(s)

        # if self.config.Parameters.vmtouch_cache_cwd:
        #    self.vmtouch_files = "'"+self.vmtouch_files+"' '"+self.cwd+"/'" Commented out as fix for #1941
        self.command = f"{vmtouch_available} {vmtouch_flags} {vmtouch_file_size} {self.vmtouch_files} && {self.command}"

    def _vmtouch_free(self):
        subprocess.Popen(
            "kill $(pidof vmtouch)",
            shell=True,
            env=self.env,
            cwd=self.cwd,
        )
        if not self.vmtouch_files:
            return

        vmtouch_flags = "-e -v"
        command = f"{vmtouch_available} {vmtouch_flags} {self.vmtouch_files}"
        subprocess.Popen(
            command,
            shell=True,
            env=self.env,
            cwd=self.cwd,
        )

    def run(self) -> Result[str | None]:
        """
        Run command with pre-configured parameters

        :return: `status` is True if command executed successfully,
                 `data` may be available even if `status` is False.
        """
        if None in [self.runner, self.env]:
            return Result(
                False, message="runner or env is not ready, Wine command terminated."
            )

        if vmtouch_available and self.config.Parameters.vmtouch and not self.terminal:
            self._vmtouch_preload()

        # run command in external terminal if terminal is True
        if self.terminal:
            return Result(
                status=TerminalUtils().execute(
                    self.command, self.env, self.colors, self.cwd
                )
            )

        # prepare proc if we are going to execute command internally
        # proc should always be `Popen[bytes]` to make sure
        # stdout_data's type is `bytes`
        proc: subprocess.Popen[bytes]
        try:
            proc = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                shell=True,
                env=self.env,
                cwd=self.cwd,
            )
        except FileNotFoundError:
            return Result(False, message="File not found")

        stdout_data, _ = proc.communicate()

        if vmtouch_available and self.config.Parameters.vmtouch:
            # don't call vmtouch_free while running via external terminal
            self._vmtouch_free()

        # Consider changing the locale to C.UTF-8 when
        # executing commands, to ensure consistent output and
        # enable callers to make use of the returned value,
        # also without requiring the encoding detection dance
        codec = detect_encoding(stdout_data)
        rv: str
        try:
            rv = stdout_data.decode(codec)
        except (UnicodeDecodeError, LookupError, TypeError):
            # UnicodeDecodeError: codec mismatch
            # LookupError: unknown codec name
            # TypeError: codec is None
            logging.warning("stdout decoding failed")
            rv = str(stdout_data)[2:-1]  # trim b''

        # "ShellExecuteEx" exception may occur while executing command,
        # previously we rerun the command without `cwd` and `stdout=PIPE`
        # to fix it, which is removed since it may lead to unexpected behavior
        if "ShellExecuteEx" in rv:
            logging.warning("ShellExecuteEx exception seems occurred.")
            return Result(
                False, data=rv, message="ShellExecuteEx exception seems occurred."
            )

        return Result(True, data=rv)
