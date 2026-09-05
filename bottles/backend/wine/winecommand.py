import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
from typing import Iterable, Optional

from bottles.backend.globals import (
    Paths,
    gamemode_available,
    gamescope_available,
    is_cpak,
    lsfg_vk_version,
    mangohud_available,
    obs_vkc_available,
    vmtouch_available,
)
from bottles.backend.logger import Logger
from bottles.backend.managers.runtime import RuntimeManager
from bottles.backend.managers.sandbox import SandboxManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.display import DisplayUtils
from bottles.backend.utils.generic import (
    detect_encoding,
    get_host_architecture,
    is_ntsync_available,
)
from bottles.backend.utils.gpu import GPUUtils
from bottles.backend.utils.hidraw import normalize_hidraw_id
from bottles.backend.utils.lsfgvk import get_lsfg_vk_dll_path
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.steam import SteamUtils
from bottles.backend.utils.terminal import TerminalUtils

logging = Logger()


def _is_enabled_value(value) -> bool:
    return value not in (None, "", "0", False)


class WineEnv:
    """
    This class is used to store and return a command environment.
    """

    __env: dict = {}
    __result: dict = {"envs": {}, "overrides": []}

    def __init__(self, clean: bool = False, allowed_keys: Optional[Iterable[str]] = None):
        self.__env = {}
        if clean:
            return

        if allowed_keys is None:
            self.__env = os.environ.copy()
            return

        for key in allowed_keys:
            if not isinstance(key, str):
                continue
            if key in os.environ:
                self.__env[key] = os.environ[key]

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

    def get_value(self, key):
        return self.__env.get(key)

    def is_enabled(self, key):
        return _is_enabled_value(self.__env.get(key))


def _proton_option_enabled(get_value, option: str) -> bool:
    for key in (f"PROTON_USE_{option}", f"PROTON_ENABLE_{option}"):
        value = get_value(key)
        if value is not None:
            return _is_enabled_value(value)
    return False


def _wayland_requested(env: "WineEnv", params) -> bool:
    return getattr(params, "wayland", False) or _proton_option_enabled(
        env.get_value, "WAYLAND"
    )


def _wayland_available(env: "WineEnv") -> bool:
    return DisplayUtils.display_server_type() == "wayland" and bool(
        env.has("WAYLAND_DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )


def apply_wayland_preferences(
    env: "WineEnv", params, xlocale_dir: Optional[str] = None
) -> None:
    proton_wayland_enabled = _proton_option_enabled(env.get_value, "WAYLAND")
    if not _wayland_requested(env, params):
        return
    if DisplayUtils.display_server_type() != "wayland":
        return
    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    if not env.has("WAYLAND_DISPLAY") and wayland_display:
        env.add("WAYLAND_DISPLAY", wayland_display, override=True)
    if env.has("WAYLAND_DISPLAY") or wayland_display:
        if proton_wayland_enabled:
            if env.has("PROTON_WAYLAND_MONITOR"):
                env.add(
                    "WAYLANDDRV_PRIMARY_MONITOR",
                    env.get_value("PROTON_WAYLAND_MONITOR"),
                    override=True,
                )
            env.concat(
                "WINEDLLOVERRIDES",
                ["winex11.drv=d", "winewayland.drv=b"],
                sep=";",
            )
            env.add("WINE_USE_EGL", "1", override=True)
            env.add("WINE_DISABLE_FULLSCREEN_HACK", "1", override=True)
            env.add("WINE_MOVE_HACK", "1")
            env.add("PROTON_USE_XALIA", "0", override=True)
            env.add("PROTON_NO_STEAMINPUT", "1", override=True)
            env.remove("SteamVirtualGamepadInfo")
            env.remove("SDL_GAMECONTROLLER_IGNORE_DEVICES")
            env.remove("SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD")
            if xlocale_dir:
                env.add("XLOCALEDIR", xlocale_dir)
        env.remove("DISPLAY")


def apply_hdr_preferences(env: "WineEnv", params, gamescope_activated: bool) -> None:
    if gamescope_activated:
        env.remove("ENABLE_HDR_WSI")

    hdr_enabled = getattr(params, "hdr", False) or _proton_option_enabled(
        env.get_value, "HDR"
    )
    if not hdr_enabled:
        return

    if not gamescope_activated and not (
        _wayland_requested(env, params) and _wayland_available(env)
    ):
        return

    env.add("DXVK_HDR", "1")
    if gamescope_activated:
        env.remove("DISABLE_GAMESCOPE_WSI")
        env.add("ENABLE_GAMESCOPE_WSI", "1", override=True)


def apply_lsfg_vk_preferences(
    env: "WineEnv", params, bottle_path: str, version: Optional[int] = None
) -> None:
    if version is None:
        version = lsfg_vk_version

    if not getattr(params, "lsfg_vk", False):
        return

    dll = get_lsfg_vk_dll_path(bottle_path)
    try:
        multiplier = int(getattr(params, "lsfg_vk_multiplier", 2))
        flow_scale = float(getattr(params, "lsfg_vk_flow_scale", 1.0))
    except (TypeError, ValueError):
        multiplier = 0
        flow_scale = 0
    enabled = (
        version in (1, 2)
        and os.path.isfile(dll)
        and os.access(dll, os.R_OK)
        and 2 <= multiplier <= 4
        and 0.25 <= flow_scale <= 1.0
    )
    if not enabled:
        env.add("DISABLE_LSFG", "1", override=True)
        env.add("DISABLE_LSFGVK", "1", override=True)
        return

    multiplier = str(multiplier)
    flow_scale = str(flow_scale)
    performance = "1" if getattr(params, "lsfg_vk_performance_mode", False) else "0"

    if version == 2:
        env.add("DISABLE_LSFG", "1", override=True)
        env.remove("DISABLE_LSFGVK")
        env.add("LSFGVK_ENV", "1", override=True)
        env.add("LSFGVK_DLL_PATH", dll, override=True)
        env.add("LSFGVK_MULTIPLIER", multiplier, override=True)
        env.add("LSFGVK_FLOW_SCALE", flow_scale, override=True)
        env.add("LSFGVK_PERFORMANCE_MODE", performance, override=True)
        return

    env.remove("DISABLE_LSFG")
    env.add("DISABLE_LSFGVK", "1", override=True)
    env.add("LSFG_LEGACY", "1", override=True)
    env.add("LSFG_DLL_PATH", dll, override=True)
    env.add("LSFG_MULTIPLIER", multiplier, override=True)
    env.add("LSFG_FLOW_SCALE", flow_scale, override=True)
    env.add("LSFG_PERFORMANCE_MODE", performance, override=True)


def apply_frame_rate_limit(env: "WineEnv", params) -> None:
    try:
        limit = int(getattr(params, "frame_rate_limit", 0))
    except (TypeError, ValueError):
        return

    if limit <= 0:
        return

    dxvk_config = env.get_value("DXVK_CONFIG")
    frame_rate_config = (
        f"dxgi.maxFrameRate = {limit}; d3d9.maxFrameRate = {limit}"
    )
    if dxvk_config:
        frame_rate_config = f"{dxvk_config.rstrip('; ')}; {frame_rate_config}"

    env.add("DXVK_CONFIG", frame_rate_config, override=True)
    env.add("VKD3D_FRAME_RATE", str(limit), override=True)


def apply_hidraw_preferences(env: "WineEnv", params) -> None:
    selected = []
    for value in getattr(params, "hidraw_devices", []):
        identifier = normalize_hidraw_id(value)
        if identifier and identifier not in selected:
            selected.append(identifier)

    if selected:
        env.add("PROTON_ENABLE_HIDRAW", ",".join(selected), override=True)


def apply_openxr_preferences(
    env: "WineEnv", runner_name: str, runner_path: str, bottle_path: str
) -> None:
    if not runner_name.lower().startswith("soda-"):
        return

    source = os.path.join(runner_path, "share/openxr/wineopenxr64.json")
    if not os.path.isfile(source):
        return

    target_dir = os.path.join(bottle_path, "drive_c/openxr")
    try:
        bottle_root = os.path.realpath(bottle_path)
        target_parent = os.path.realpath(os.path.dirname(target_dir))
        if os.path.commonpath((bottle_root, target_parent)) != bottle_root:
            raise OSError("OpenXR manifest path escapes the bottle")

        os.makedirs(target_dir, exist_ok=True)
        if os.path.commonpath(
            (bottle_root, os.path.realpath(target_dir))
        ) != bottle_root:
            raise OSError("OpenXR manifest path escapes the bottle")

        with open(source, "rb") as manifest:
            data = manifest.read(4097)
        if len(data) > 4096 or b"wineopenxr.dll" not in data:
            raise OSError("Invalid OpenXR manifest")

        target = os.path.join(target_dir, "wineopenxr64.json")
        if os.path.isfile(target):
            with open(target, "rb") as current:
                if current.read(4097) == data:
                    env.add("SODA_OPENXR_RUNTIME", "host")
                    return

        fd, temporary = tempfile.mkstemp(prefix=".wineopenxr-", dir=target_dir)
        try:
            with os.fdopen(fd, "wb") as manifest:
                manifest.write(data)
                manifest.flush()
                os.fsync(manifest.fileno())
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
        env.add("SODA_OPENXR_RUNTIME", "host")
    except OSError as error:
        logging.warning(f"Could not prepare Soda OpenXR: {error}")


def apply_fex_preferences(env: "WineEnv", runner_name: str, runner_path: str) -> None:
    if (
        get_host_architecture() != "aarch64"
        or not runner_name.lower().startswith("soda-")
    ):
        return

    config = os.path.join(runner_path, "share/fex-emu/Config.json")
    unixlib = os.path.join(runner_path, "lib/wine/aarch64-unix/libwow64fex.so")
    if not os.path.isfile(config) or not os.path.isfile(unixlib):
        return

    env.add("FEX_APP_CONFIG", config)
    env.add("FEX_APP_CONFIG_LOCATION", os.path.dirname(config))


def _needs_steam_virtual_gamepad_workaround(runner_name: Optional[str]) -> bool:
    """Return True if the runner should force SteamVirtualGamepadInfo."""

    if not runner_name:
        return False

    normalized = runner_name.lower()
    if not any(
        prefix in normalized for prefix in ("ge-proton", "proton-ge", "wine-ge", "soda")
    ):
        return False

    match = re.search(r"(\d+)", normalized)
    if not match:
        return False

    try:
        major = int(match.group(1))
    except ValueError:
        return False

    return major <= 8


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
        pre_script: Optional[str] = None,
        post_script: Optional[str] = None,
        pre_script_args: Optional[str] = None,
        post_script_args: Optional[str] = None,
        cwd: Optional[str] = None,
        sandbox_override: Optional[str] = None,
        forced_dll_overrides: Optional[str] = None,
    ):
        _environment = environment.copy()
        self.config = self._get_config(config)
        self.forced_dll_overrides = forced_dll_overrides
        self.minimal = minimal
        # Per-launch override of the dedicated sandbox decided in the config:
        #   None  -> follow the bottle setting
        #   "off" -> run this launch without the dedicated sandbox
        self.sandbox_override = sandbox_override
        self.arguments = arguments
        self.cwd = self._get_cwd(cwd)
        self.runner, self.runner_runtime = self._get_runner_info()
        self.gamescope_activated = (
            environment["GAMESCOPE"] == "1"
            if "GAMESCOPE" in environment
            else self.config.Parameters.gamescope
        )
        self.command = self.get_cmd(
            command,
            pre_script,
            post_script,
            pre_script_args,
            post_script_args,
            environment=_environment,
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

        if config.Environment == "Steam":
            bottle = config.Path
        else:
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
        environment: Optional[dict] = None,
        return_steam_env: bool = False,
        return_clean_env: bool = False,
    ) -> dict:
        config = self.config
        clean_env = return_steam_env or return_clean_env
        allowed_env_keys: Optional[Iterable[str]] = None
        if not clean_env and getattr(config, "Limit_System_Environment", False):
            allowed_env_keys = config.Inherited_Environment_Variables

        env = WineEnv(clean=clean_env, allowed_keys=allowed_env_keys)
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
        proton_path = ""

        if config.Environment == "Steam":
            bottle = config.Path
            runner_path = config.RunnerPath

        if SteamUtils.is_proton(runner_path):
            proton_path = runner_path
            SteamUtils.sync_proton_vkd3d(runner_path, bottle, arch)
            SteamUtils.sync_proton_fonts(runner_path, bottle)
            runner_path = SteamUtils.get_dist_directory(runner_path)

        # Clean some env variables which can cause trouble
        # ref: <https://github.com/bottlesdevs/Bottles/issues/2127>
        # env.remove("XDG_DATA_HOME")

        dll_overrides = []
        gpu = GPUUtils().get_gpu()
        DisplayUtils.check_nvidia_device()
        ld = []

        # Bottle environment variables
        if _needs_steam_virtual_gamepad_workaround(config.Runner) and not env.has(
            "SteamVirtualGamepadInfo"
        ):
            env.add("SteamVirtualGamepadInfo", "", override=True)

        if config.Environment_Variables:
            for key, value in config.Environment_Variables.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    logging.warning(f"Ignoring malformed environment variable {key!r}")
                    continue
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

        apply_openxr_preferences(env, config.Runner, runner_path, bottle)
        apply_fex_preferences(env, config.Runner, runner_path)

        # Language
        if config.Language != "sys":
            # ensure an encoding is set (e.g. zh_CN -> zh_CN.UTF-8), otherwise
            # wine renders non-Latin text as garbage
            language = config.Language
            if "." not in language:
                language = f"{language}.UTF-8"
            env.add("LC_ALL", language)

        # Bottle DLL_Overrides
        if config.DLL_Overrides:
            for k, v in config.DLL_Overrides.items():
                dll_overrides.append(f"{k}={v}")

        # Default DLL overrides
        if not return_steam_env:
            dll_overrides.append("winemenubuilder=''")

        # Get Runtime libraries
        if (
            (params.use_runtime or params.use_eac_runtime or params.use_be_runtime)
            and not self.terminal
            and not return_steam_env
        ):
            _rb = RuntimeManager.get_runtime_env("bottles")
            if _rb:
                _eac = RuntimeManager.get_eac()
                _be = RuntimeManager.get_be()

                if params.use_runtime:
                    logging.info("Using Bottles runtime")
                    ld += _rb

                if (
                    _eac and not self.minimal
                ):  # NOTE: should check for runner compatibility with "eac" (?)
                    logging.info("Using EasyAntiCheat runtime")
                    env.add("PROTON_EAC_RUNTIME", _eac)
                    dll_overrides.append("easyanticheat_x86,easyanticheat_x64=b,n")

                if (
                    _be and not self.minimal
                ):  # NOTE: should check for runner compatibility with "be" (?)
                    logging.info("Using BattlEye runtime")
                    env.add("PROTON_BATTLEYE_RUNTIME", _be)
                    dll_overrides.append("beclient,beclient_x64=b,n")
            else:
                logging.warning("Bottles runtime was requested but not found")

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

        if get_host_architecture() == "aarch64":
            runner_libs.insert(2, "lib/wine/aarch64-unix")

        if not config.Runner.startswith("sys-"):
            for lib in runner_libs:
                _path = os.path.join(runner_path, lib)
                if os.path.exists(_path):
                    ld.append(_path)

            # Embedded GStreamer environment variables
            if not env.has("BOTTLES_USE_SYSTEM_GSTREAMER") and not return_steam_env:
                gst_env_path = []
                for lib in gst_libs:
                    if os.path.exists(os.path.join(runner_path, lib)):
                        gst_env_path.append(os.path.join(runner_path, lib))
                if len(gst_env_path) > 0:
                    env.add("GST_PLUGIN_SYSTEM_PATH", ":".join(gst_env_path), override=True)

        # DXVK environment variables
        if params.dxvk and not return_steam_env:
            env.add("WINE_LARGE_ADDRESS_AWARE", "1")
            env.add(
                "DXVK_SHADER_CACHE_PATH", os.path.join(bottle, "cache", "dxvk_shader")
            )
            env.add("STAGING_SHARED_MEMORY", "1")
            env.add("__GL_SHADER_DISK_CACHE", "1")
            env.add(
                "__GL_SHADER_DISK_CACHE_PATH",
                os.path.join(bottle, "cache", "gl_shader"),
            )
            env.add(
                "MESA_SHADER_CACHE_DIR", os.path.join(bottle, "cache", "mesa_shader")
            )

        # VKD3D environment variables
        if params.vkd3d and not return_steam_env:
            env.add(
                "VKD3D_SHADER_CACHE_PATH", os.path.join(bottle, "cache", "vkd3d_shader")
            )

        apply_frame_rate_limit(env, params)
        apply_hidraw_preferences(env, params)

        # LatencyFleX environment variables
        if params.latencyflex and not return_steam_env:
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
                env.add("MANGOHUD_CONFIG", "read_cfg,no_display")

        # vkBasalt environment variables
        if params.vkbasalt and not self.minimal:
            vkbasalt_conf_path = os.path.join(
                ManagerUtils.get_bottle_path(config), "vkBasalt.conf"
            )
            if os.path.isfile(vkbasalt_conf_path):
                env.add("VKBASALT_CONFIG_FILE", vkbasalt_conf_path)
            env.add("ENABLE_VKBASALT", "1")

        apply_lsfg_vk_preferences(
            env,
            params,
            bottle,
            version=lsfg_vk_version if arch != "win32" and not self.minimal else 0,
        )

        # OBS Vulkan Capture environment variables
        if params.obsvkc and not self.minimal:
            env.add("OBS_VKCAPTURE", "1")
            if DisplayUtils.display_server_type() == "x11":
                env.add("OBS_USE_EGL", "1")

        # DXVK-Nvapi environment variables
        if params.dxvk_nvapi and not return_steam_env:
            # NOTE: users reported that DXVK_ENABLE_NVAPI and DXVK_NVAPIHACK must be set to make
            #       DLSS works. I don't have a GPU compatible with this tech, so I'll trust them
            env.add("DXVK_NVAPIHACK", "0")
            env.add("DXVK_ENABLE_NVAPI", "1")

        self._apply_sync_environment(env, params.sync, self.runner)

        # Wine debug level
        if not return_steam_env:
            debug_level = "fixme-all"
            if params.fixme_logs:
                debug_level = "+fixme-all"
            env.add("WINEDEBUG", debug_level)

        # Aco compiler
        # if params["aco_compiler"]:
        #     env.add("ACO_COMPILER", "aco")

        # PulseAudio latency
        if params.pulseaudio_latency:
            env.add("PULSE_LATENCY_MSEC", "60")

        # Discrete GPU
        if not return_steam_env:
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
        if getattr(self, "forced_dll_overrides", None):
            dll_overrides.append(self.forced_dll_overrides)
        env.concat("WINEDLLOVERRIDES", dll_overrides, sep=";")
        if env.is_empty("WINEDLLOVERRIDES"):
            env.remove("WINEDLLOVERRIDES")

        if not return_steam_env:
            # Wine prefix
            env.add("WINEPREFIX", bottle, override=True)
            # Wine arch
            env.add("WINEARCH", arch)

        xlocale_dir = None
        if runner_path:
            candidate = os.path.join(runner_path, "share/X11/locale")
            if os.path.isdir(candidate):
                xlocale_dir = candidate
        apply_wayland_preferences(env, params, xlocale_dir)
        apply_hdr_preferences(
            env,
            params,
            bool(not self.minimal and gamescope_available and self.gamescope_activated),
        )

        resolved_env = env.get()["envs"]
        if proton_path and not clean_env and not self.minimal:
            proton_sandbox = None
            if params.sandbox:
                proton_sandbox = SandboxManager(
                    chdir=bottle,
                    clear_env=True,
                    share_paths_ro=[proton_path],
                    share_paths_rw=[bottle],
                    share_net=config.Sandbox.share_net,
                    share_display=False,
                    share_sound=False,
                    share_gpu=False,
                )
            SteamUtils.prepare_proton_fsr4(
                proton_path, bottle, resolved_env, proton_sandbox
            )

        return resolved_env

    @staticmethod
    def _apply_sync_environment(env: WineEnv, sync: str, runner: str) -> None:
        if sync == "esync":
            env.add("WINEESYNC", "1")
        elif sync == "fsync":
            env.add("WINEFSYNC", "1")
        elif sync in ("wine", "ntsync"):
            if is_ntsync_available(runner):
                env.add("WINENTSYNC", "1")
            elif sync == "ntsync":
                logging.warning(
                    "ntsync requested but unavailable, falling back to fsync"
                )
                env.add("WINEFSYNC", "1")

    def _get_runner_info(self) -> tuple[str, str]:
        config = self.config
        runner = ManagerUtils.get_runner_path(config.Runner)
        arch = config.Arch
        runner_runtime = ""

        if config.Environment == "Steam":
            runner = config.RunnerPath

        if runner in [None, ""]:
            return "", ""

        if SteamUtils.is_proton(runner):
            """
            If the runner is Proton, set the path to /dist or /files
            based on check if files exists.
            Additionally, check for its corresponding runtime.
            """
            runner_runtime = SteamUtils.get_associated_runtime(runner)
            runner = os.path.join(SteamUtils.get_dist_directory(runner), "bin/wine")

        elif runner.startswith("sys-"):
            """
            If the runner type is system, set the runner binary
            path to the system command. Else set it to the full path.
            """
            runner = shutil.which("wine")

        else:
            runner = f"{runner}/bin/wine"

        if arch == "win64" and os.path.exists(f"{runner}64"):
            runner = f"{runner}64"

        runner = shlex.quote(runner)  # type: ignore

        return runner, runner_runtime

    def get_cmd(
        self,
        command,
        pre_script: Optional[str] = None,
        post_script: Optional[str] = None,
        pre_script_args: Optional[str] = None,
        post_script_args: Optional[str] = None,
        return_steam_cmd: bool = False,
        return_clean_cmd: bool = False,
        environment: Optional[dict] = None,
    ) -> str:
        config = self.config
        params = config.Parameters
        runner = self.runner
        self.steam_runtime_root = ""

        if environment is None:
            environment = {}

        launch_prefix, launch_suffix = "", ""
        if self.arguments:
            launch_prefix, launch_suffix, launch_environment = (
                SteamUtils.handle_launch_options(self.arguments)
            )
            if launch_environment.get("WINEDLLOVERRIDES") and environment.get(
                "WINEDLLOVERRIDES"
            ):
                environment["WINEDLLOVERRIDES"] += ";" + launch_environment.pop(
                    "WINEDLLOVERRIDES"
                )
            environment.update(launch_environment)

        if return_clean_cmd:
            return_steam_cmd = True

        if not return_steam_cmd and not return_clean_cmd:
            command = f"{runner} {command}"

        if params.use_steam_runtime:
            _rs = RuntimeManager.get_runtimes("steam")
            _picked = {}

            if _rs:
                if "steamrt4" in _rs.keys() and "steamrt4" in self.runner_runtime:
                    """
                    Steam Linux Runtime 4 (steamrt4) is the default runtime used by Proton version >= 11.0
                    """
                    _picked = _rs["steamrt4"]
                elif "sniper" in _rs.keys() and "sniper" in self.runner_runtime:
                    """
                    Sniper is the default runtime used by Proton version >= 8.0 and < 11.0
                    """
                    _picked = _rs["sniper"]
                elif "soldier" in _rs.keys() and "soldier" in self.runner_runtime:
                    """
                    Sniper is the default runtime used by Proton version >= 5.13 and < 8.0
                    """
                    _picked = _rs["soldier"]
                elif "scout" in _rs.keys():
                    """
                    For Wine runners, we cannot make assumption about which runtime would suits
                    them the best, as it would depend on their build environment.
                    Sniper/Soldier are not backward-compatible, defaulting to Scout should maximize compatibility.
                    """
                    _picked = _rs["scout"]
            else:
                logging.warning("Steam runtime was requested but not found")

            if _picked:
                logging.info(f"Using Steam runtime {_picked['name']}")
                entry_point = os.path.realpath(_picked["entry_point"])
                self.steam_runtime_root = os.path.dirname(entry_point)
                separator = "-- " if _picked["name"] != "scout" else ""
                command = f"{entry_point} {separator}{command}"
            else:
                logging.warning(
                    "Steam runtime was requested and found but there are no valid combinations"
                )

        if not self.minimal:
            if gamemode_available and params.gamemode:
                if not return_steam_cmd:
                    command = f"{gamemode_available} {command}"
                else:
                    command = f"gamemode {command}"

            if mangohud_available and params.mangohud and not self.gamescope_activated:
                if not return_steam_cmd:
                    command = f"{mangohud_available} {command}"
                else:
                    command = f"mangohud {command}"

            if gamescope_available and self.gamescope_activated:
                # Write the script into Bottles' temp dir (shared with the
                # dedicated sandbox) instead of the system /tmp, otherwise
                # Gamescope running inside the sandbox cannot see it.
                os.makedirs(Paths.temp, exist_ok=True)
                gamescope_payload = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".sh", dir=Paths.temp
                ).name
                gamescope_reaper = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", dir=Paths.temp
                ).name

                payload = ["#!/usr/bin/env sh\n"]
                payload.append(f'{command} "$@"')
                if mangohud_available and params.mangohud:
                    payload.append(" &\nmangoapp")
                with open(gamescope_payload, "w") as f:
                    f.write("".join(payload))
                os.chmod(
                    gamescope_payload,
                    os.stat(gamescope_payload).st_mode | stat.S_IEXEC,
                )

                reaper = """#!/usr/bin/env python3
import ctypes
import os
import signal
import subprocess
import sys
import time


def descendants():
    pending = [os.getpid()]
    found = []
    while pending:
        parent = pending.pop()
        try:
            children = open(
                f"/proc/{parent}/task/{parent}/children", encoding="ascii"
            ).read()
        except OSError:
            continue
        for value in children.split():
            child = int(value)
            if child not in found:
                found.append(child)
                pending.append(child)
    return found


if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
    os.execv(sys.argv[1], sys.argv[1:])

process = subprocess.Popen(sys.argv[1:])
status = process.wait()
for sig in (signal.SIGTERM, signal.SIGKILL):
    for child in descendants():
        try:
            os.kill(child, sig)
        except ProcessLookupError:
            pass
    if sig == signal.SIGTERM:
        deadline = time.monotonic() + 0.5
        while descendants() and time.monotonic() < deadline:
            time.sleep(0.05)

while True:
    try:
        child, _ = os.waitpid(-1, os.WNOHANG)
        if child == 0:
            break
    except ChildProcessError:
        break
raise SystemExit(status if status >= 0 else 128 - status)
"""
                with open(gamescope_reaper, "w") as f:
                    f.write(reaper)
                os.chmod(
                    gamescope_reaper,
                    os.stat(gamescope_reaper).st_mode | stat.S_IEXEC,
                )

                # Update command
                command = (
                    f"{self._get_gamescope_cmd(return_steam_cmd, environment)} -- "
                    f"{shlex.quote(gamescope_reaper)} {shlex.quote(gamescope_payload)}"
                )
                logging.info(f"Running Gamescope command: '{command}'")
                logging.info(f"{gamescope_payload} contains:")
                with open(gamescope_payload, "r") as f:
                    logging.info(f"\n\n{f.read()}")

            if obs_vkc_available and params.obsvkc:
                command = f"{obs_vkc_available} {command}"

        if self.arguments:
            if launch_prefix:
                command = f"{launch_prefix} {command}"
            if launch_suffix:
                command = f"{command} {launch_suffix}"

        if post_script not in (None, ""):
            post_cmd_parts = [post_script]
            if post_script_args not in (None, ""):
                post_cmd_parts.extend(shlex.split(post_script_args))
            post_cmd = " ".join(shlex.quote(part) for part in post_cmd_parts)
            command = f"{command} ; sh {post_cmd}"

        if pre_script not in (None, ""):
            pre_cmd_parts = [pre_script]
            if pre_script_args not in (None, ""):
                pre_cmd_parts.extend(shlex.split(pre_script_args))
            pre_cmd = " ".join(shlex.quote(part) for part in pre_cmd_parts)
            command = f"sh {pre_cmd} ; {command}"

        return command

    def _get_gamescope_cmd(
        self,
        return_steam_cmd: bool = False,
        environment: Optional[dict] = None,
    ) -> str:
        config = self.config
        params = config.Parameters
        gamescope_cmd = []

        if gamescope_available and self.gamescope_activated:
            gamescope_cmd = [gamescope_available]
            gamescope_extension = "/usr/lib/extensions/vulkan/gamescope"
            if gamescope_available.startswith(f"{gamescope_extension}/"):
                gamescope_cmd = [
                    "env",
                    f"LD_LIBRARY_PATH={gamescope_extension}/lib${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}",
                    gamescope_available,
                ]
            if return_steam_cmd:
                gamescope_cmd = ["gamescope"]
            effective_environment = config.Environment_Variables.copy()
            effective_environment.update(environment or {})
            hdr_enabled = params.hdr or _proton_option_enabled(
                effective_environment.get, "HDR"
            )
            if (
                hdr_enabled
                and "--hdr-enabled" not in params.gamescope_custom_options.split()
            ):
                gamescope_cmd.append("--hdr-enabled")
            if params.gamescope_custom_options:
                gamescope_cmd.append(params.gamescope_custom_options)
            if params.gamescope_fullscreen:
                gamescope_cmd.append("-f")
            if params.gamescope_borderless:
                gamescope_cmd.append("-b")
            if params.gamescope_scaling:
                gamescope_cmd.append("-S integer")
            if params.fsr:
                gamescope_cmd.append("-F fsr")
                gamescope_cmd.append(
                    f"--fsr-sharpness {params.fsr_sharpening_strength}"
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
        try:
            last_token = shlex.split(self.command)[-1]
        except (ValueError, IndexError):
            last_token = self.command.split(" ")[-1]
        if self.command.find("C:\\") > 0:
            s = (self.cwd + "/" + last_token.split("\\")[-1]).replace("'", "")
        else:
            s = last_token
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

    def _get_sandbox_manager(self) -> SandboxManager:
        # Steam/Proton runners live outside Paths.runners (in the Steam data
        # directory) and rely on their associated Steam Linux Runtime. Expose
        # the runner root and that runtime, otherwise the runtime's own bwrap
        # cannot find its entry point inside the dedicated sandbox. Symlinks are
        # resolved so the real target gets shared, not just the link.
        share_paths_ro = [Paths.runners, Paths.temp]
        cpak_grants = "/run/cpak/grants"
        if is_cpak() and os.path.isdir(cpak_grants):
            share_paths_ro.append(cpak_grants)

        runner_root = (
            self.config.RunnerPath
            if self.config.Environment == "Steam" and self.config.RunnerPath
            else ManagerUtils.get_runner_path(self.config.Runner)
        )
        for extra in (runner_root, self.steam_runtime_root):
            if extra and not str(extra).startswith("sys-"):
                share_paths_ro.append(os.path.realpath(extra))

        # The working directory may be a transient document portal path
        # (/run/user/<uid>/doc/<id>/...) which is not reliably reachable inside
        # the nested sandbox: it can disappear or simply not be accessible to
        # bwrap's chdir, which would make nothing launch at all. Resolve it to a
        # real host path and fall back to the bottle path (always exposed and
        # present) whenever it is not a usable directory.
        bottle_path = ManagerUtils.get_bottle_path(self.config)
        chdir = ManagerUtils.resolve_portal_path(self.cwd) if self.cwd else bottle_path
        if (
            not chdir
            or ("/run/user/" in chdir and "/doc/" in chdir)
            or not os.path.isdir(chdir)
        ):
            logging.warning(
                f"Working directory '{self.cwd}' is not usable inside the "
                "dedicated sandbox, falling back to the bottle path.",
                jn=True,
            )
            chdir = bottle_path

        share_paths_rw = [bottle_path]
        for value in (
            getattr(self, "arguments", ""),
            getattr(self, "command", ""),
        ):
            try:
                arguments = shlex.split(value)
            except ValueError:
                continue
            for argument in arguments:
                if (
                    ManagerUtils.is_portal_document_path(argument)
                    and argument not in share_paths_rw
                ):
                    share_paths_rw.append(argument)

        hidraw_selected = any(
            normalize_hidraw_id(value)
            for value in self.config.Parameters.hidraw_devices
        )
        return SandboxManager(
            envs=self.env,
            chdir=chdir,
            clear_env=True,
            share_paths_rw=share_paths_rw,
            share_paths_ro=[p for p in share_paths_ro if p],
            share_net=self.config.Sandbox.share_net,
            share_sound=self.config.Sandbox.share_sound,
            share_input=self.config.Sandbox.share_input or hidraw_selected,
            share_usb=self.config.Sandbox.share_usb or hidraw_selected,
            share_hidraw=hidraw_selected,
        )

    def run(self) -> Result[Optional[str]]:
        """
        Run command with pre-configured parameters

        :return: `status` is True if command executed successfully,
                 `data` may be available even if `status` is False.
        """
        if None in [self.runner, self.env]:
            return Result(
                False, message="runner or env is not ready, Wine command terminated."
            )

        # Log the final command that will be executed
        logging.info(f"Executing command: {self.command}")

        if vmtouch_available and self.config.Parameters.vmtouch and not self.terminal:
            self._vmtouch_preload()

        use_sandbox = self.config.Parameters.sandbox
        if self.sandbox_override == "off":
            use_sandbox = False
            logging.warning(
                "Launching without the dedicated sandbox on user request: the "
                "target is outside the bottle and cannot be reached otherwise.",
                jn=True,
            )
        sandbox = self._get_sandbox_manager() if use_sandbox else None

        # run command in external terminal if terminal is True
        if self.terminal:
            if sandbox:
                return Result(
                    status=TerminalUtils().execute(
                        sandbox.get_cmd(self.command), self.env, self.colors, self.cwd
                    )
                )
            else:
                return Result(
                    status=TerminalUtils().execute(
                        self.command, self.env, self.colors, self.cwd
                    )
                )

        # prepare proc if we are going to execute command internally
        # proc should always be `Popen[bytes]` to make sure
        # stdout_data's type is `bytes`
        proc: subprocess.Popen[bytes]
        if sandbox:
            proc = sandbox.run(self.command)
        else:
            try:
                proc = subprocess.Popen(
                    self.command,
                    stdout=subprocess.PIPE,
                    shell=True,
                    env=self.env,
                    cwd=self.cwd,
                    start_new_session=True,
                )
            except FileNotFoundError:
                return Result(False, message="File not found")

        if not self.communicate:
            return Result(True)

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

        if proc.returncode:
            return Result(
                False,
                data=rv,
                message=f"Command exited with status {proc.returncode}.",
            )

        # "ShellExecuteEx" exception may occur while executing command,
        # previously we rerun the command without `cwd` and `stdout=PIPE`
        # to fix it, which is removed since it may lead to unexpected behavior
        if "ShellExecuteEx" in rv:
            logging.warning("ShellExecuteEx exception seems occurred.")
            return Result(
                False, data=rv, message="ShellExecuteEx exception seems occurred."
            )

        return Result(True, data=rv)
