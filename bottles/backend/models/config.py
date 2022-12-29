import logging
import os
from dataclasses import dataclass, field, replace, asdict
from io import IOBase
from typing import List, Dict, Union, Optional

from typing.io import IO

from bottles.backend.models.result import Result
from bottles.backend.utils import yaml


# class name prefix "Bottle" is a workaround for:
# https://github.com/python/cpython/issues/90104


# noinspection PyDataclass
class DictCompatMixIn:
    def keys(self):
        return self.__dict__.keys()

    def get(self, key, __default=None):
        return getattr(self, key, __default)

    def copy(self):
        return replace(self)

    def to_dict(self) -> dict:
        return asdict(self)

    def __iter__(self):
        return iter(self.__dict__)

    def __getitem__(self, item):
        return getattr(self, item)

    def __delitem__(self, key):
        return delattr(self, key)

    def __setitem__(self, key, value):
        return setattr(self, key, value)


@dataclass
class BottleSandboxParams(DictCompatMixIn):
    share_net: bool = False
    share_sound: bool = False
    # share_host_ro: bool = True  # TODO: implement, requires the Bottles runtime (next) for a minimal sandbox
    # share_gpu: bool = True  # TODO: implement
    # share_paths_ro: List[str] = field(default_factory=lambda: [])  # TODO: implement
    # share_paths_rw: List[str] = field(default_factory=lambda: [])  # TODO: implement


@dataclass
class BottleParams(DictCompatMixIn):
    dxvk: bool = False
    dxvk_nvapi: bool = False
    vkd3d: bool = False
    latencyflex: bool = False
    mangohud: bool = False
    obsvkc: bool = False
    vkbasalt: bool = False
    gamemode: bool = False
    gamescope: bool = False
    gamescope_game_width: int = 0
    gamescope_game_height: int = 0
    gamescope_window_width: int = 0
    gamescope_window_height: int = 0
    gamescope_fps: int = 0
    gamescope_fps_no_focus: int = 0
    gamescope_scaling: bool = False
    gamescope_borderless: bool = False
    gamescope_fullscreen: bool = True
    sync: str = "wine"
    fsr: bool = False
    custom_dpi: int = 96
    renderer: str = "gl"
    discrete_gpu: bool = False
    virtual_desktop: bool = False
    virtual_desktop_res: str = "1280x720"
    pulseaudio_latency: bool = False
    fullscreen_capture: bool = False
    take_focus: bool = False
    mouse_warp: bool = True
    decorated: bool = True
    fixme_logs: bool = False
    use_runtime: bool = False
    use_eac_runtime: bool = True
    use_be_runtime: bool = True
    use_steam_runtime: bool = False
    sandbox: bool = False
    versioning_compression: bool = False
    versioning_automatic: bool = False
    versioning_exclusion_patterns: bool = False
    vmtouch: bool = False
    vmtouch_cache_cwd: bool = False


@dataclass
class BottleConfig(DictCompatMixIn):
    Name: str = ""
    Arch: str = "win64"  # Enum: "win64", "win32"
    Windows: str = "win10"
    Runner: str = ""  # runner name, "sys-*"
    WorkingDir: str = ""
    DXVK: str = ""
    NVAPI: str = ""
    VKD3D: str = ""
    LatencyFleX: str = ""
    Path: str = ""
    Custom_Path: str = ""
    Environment: str = ""  # Enum: "Steam", "Custom"
    Creation_Date: str = ""
    Update_Date: str = ""
    Versioning: bool = False
    Versioning_Exclusion_Patterns: list = field(default_factory=list)
    State: int = 0
    Parameters: BottleParams = field(default_factory=BottleParams)
    Sandbox: BottleSandboxParams = field(default_factory=BottleSandboxParams)
    Environment_Variables: dict = field(default_factory=dict)
    Installed_Dependencies: List[str] = field(default_factory=list)
    DLL_Overrides: dict = field(default_factory=dict)
    External_Programs: Dict[str, dict] = field(default_factory=dict)
    Uninstallers: dict = field(default_factory=dict)
    session_arguments: str = ""
    run_in_terminal: bool = False
    Language: str = "sys"  # "sys", "any valid language code"

    # Section - Not Existed in Sample Config but used in code
    CompatData: str = ""
    data: dict = field(default_factory=dict)  # possible keys: "config", ...
    RunnerPath: str = ""

    def dump(self, file: Union[str, IO], mode='w', encoding=None, indent=4) -> Result:
        """
        Dump config to file

        :file: filepath str or IO-like object.
        :mode: when param 'file' is filepath, use this mode to open file, otherwise ignored.
               default is 'w'
        :encoding: file content encoding, default is None(Decide by Python IO)
        :indent: file indent width, default is 4
        """
        f = file if isinstance(file, IOBase) else open(file, mode=mode)
        try:
            yaml.dump(self.to_dict(), f, indent=indent, encoding=encoding)
            return Result(True)
        except Exception as e:
            logging.exception(e)
            return Result(False, message=str(e))
        finally:
            f.close()

    @classmethod
    def load(cls, file: Union[str, IO], mode='r') -> Result[Optional['BottleConfig']]:
        """
        Load config from file
        :file: filepath str or IO-like object.
        :mode: when param 'file' is filepath, use this mode to open file, otherwise ignored.
               default is 'r'
        """
        f= None
        try:
            if not os.path.exists(file):
                raise FileNotFoundError("Config file not exists")

            f = file if isinstance(file, IOBase) else open(file, mode=mode)

            data = yaml.load(f)
            if not isinstance(data, dict):
                raise TypeError("Config data should be dict type, but it was %s" % type(data))

            filled = cls._fill_with(data)
            if not filled.status:
                raise ValueError("Invalid Config data (%s)" % filled.message)

            return Result(True, data=filled.data)
        except Exception as e:
            logging.exception(e)
            return Result(False, message=str(e))
        finally:
            if f: f.close()

    @classmethod
    def _fill_with(cls, data: dict) -> Result[Optional['BottleConfig']]:
        """fill with dict"""
        try:
            data = data.copy()

            # TODO: [Review] config file sanitizing and fixing

            params = BottleParams(**data.pop("Parameters", {}))
            sandbox_param = BottleSandboxParams(**data.pop("Sandbox", {}))

            return Result(True, data=BottleConfig(
                Parameters=params,
                Sandbox=sandbox_param,
                **data
            ))
        except Exception as e:
            logging.exception(e)
            return Result(False, message=repr(e))
