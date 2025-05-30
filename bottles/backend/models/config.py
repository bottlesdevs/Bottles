import inspect
import logging
import os
from dataclasses import dataclass, field, replace, asdict, is_dataclass
from io import IOBase
from typing import IO, Self
from collections.abc import ItemsView, Container

from bottles.backend.models.result import Result
from bottles.backend.utils import yaml

# class name prefix "Bottle" is a workaround for:
# https://github.com/python/cpython/issues/90104


# noinspection PyDataclass
class DictCompatMixIn:
    @staticmethod
    def yaml_serialize_handler(dumper, data):
        dict_repr = data.to_dict()
        return dumper.represent_dict(dict_repr)

    @staticmethod
    def json_serialize_handler(data):
        return data.to_dict()

    def keys(self):
        return self.__dict__.keys()

    def get(self, key, __default=None):
        return getattr(self, key, __default)

    def copy(self):
        return replace(self)

    def to_dict(self) -> dict:
        return asdict(self)

    def items(self) -> ItemsView[str, Container]:
        return self.to_dict().items()

    def __iter__(self):
        """handle `for x in obj` syntax"""
        return iter(self.__dict__)

    def __getitem__(self, item):
        """handle `obj[x]` syntax"""
        return getattr(self, item)

    def __delitem__(self, key):
        """handle `del obj[x]` syntax"""
        return delattr(self, key)

    def __setitem__(self, key, value):
        """handle `obj[x] = y` syntax"""
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
    mangohud_display_on_game_start: bool = True
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
    fsr_sharpening_strength: int = 2
    fsr_quality_mode: str = "none"
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
    Arch: str = "win64"  # Enum, Use bottles.backend.models.enum.Arch
    Windows: str = "win10"
    Runner: str = ""  # runner name, "sys-*", or any installed runner name
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
    Installed_Dependencies: list[str] = field(default_factory=list)
    DLL_Overrides: dict = field(default_factory=dict)
    External_Programs: dict[str, dict] = field(default_factory=dict)
    Uninstallers: dict = field(default_factory=dict)
    session_arguments: str = ""
    run_in_terminal: bool = False
    Language: str = "sys"  # "sys", "any valid language code"

    # Section - Not Existed in Sample Config but used in code
    CompatData: str = ""
    data: dict = field(default_factory=dict)  # possible keys: "config", ...
    RunnerPath: str = ""

    def dump(self, file: str | IO, mode="w", encoding=None, indent=4) -> Result:
        """
        Dump config to file

        :param file: filepath str or IO-like object.
        :param mode: when param 'file' is filepath, use this mode to open file, otherwise ignored.
               default is 'w'
        :param encoding: file content encoding, default is None(Decide by Python IO)
        :param indent: file indent width, default is 4
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
    def load(cls, file: str | IO, mode="r") -> Result[Self]:
        """
        Load config from file

        :param file: filepath str or IO-like object.
        :param mode: when param 'file' is filepath, use this mode to open file, otherwise ignored.
               default is 'r'
        """
        f = None
        try:
            if not os.path.exists(file):
                raise FileNotFoundError("Config file not exists")

            f = file if isinstance(file, IOBase) else open(file, mode=mode)

            data = yaml.load(f)
            if not isinstance(data, dict):
                raise TypeError(
                    "Config data should be dict type, but it was %s" % type(data)
                )

            filled = cls._fill_with(data)
            if not filled.status:
                raise ValueError("Invalid Config data (%s)" % filled.message)

            return Result(True, data=filled.data)
        except Exception as e:
            logging.exception(e)
            return Result(False, message=str(e))
        finally:
            if f:
                f.close()

    @classmethod
    def _fill_with(cls, data: dict) -> Result[Self | None]:
        """fill with dict"""
        try:
            data = data.copy()
            data = cls._fix(data)

            params = BottleParams(**data.pop("Parameters", {}))
            sandbox_param = BottleSandboxParams(**data.pop("Sandbox", {}))

            return Result(
                True,
                data=BottleConfig(Parameters=params, Sandbox=sandbox_param, **data),
            )
        except Exception as e:
            logging.exception(e)
            return Result(False, message=repr(e))

    @classmethod
    def _fix(cls, data: dict) -> dict:
        """fix config data and return"""
        data = data.copy()

        # ensure Parameters field
        if "Parameters" not in data:
            data["Parameters"] = {}
        if "Sandbox" not in data:
            data["Sandbox"] = {}

        # migrate old fsr_level key to fsr_sharpening_strength
        # TODO: remove after some time
        if "fsr_level" in data["Parameters"]:
            logging.warning(
                "Migrating config key 'fsr_level' to 'fsr_sharpening_strength'"
            )
            data["Parameters"]["fsr_sharpening_strength"] = data["Parameters"].pop(
                "fsr_level"
            )

        # migrate typo fields
        if "DXVK_NVAPI" in data:
            logging.warning("Migrating config key 'DXVK_NVAPI' to 'NVAPI'")
            data["NVAPI"] = data.pop("DXVK_NVAPI")
        if "LatencyFlex" in data:
            logging.warning("Migrating config key 'LatencyFlex' to 'LatencyFleX'")
            data["LatencyFleX"] = data.pop("LatencyFlex")

        # cleanup unexpected fields
        data = cls._filter(data)

        return data

    @classmethod
    def _filter(cls, data: dict, clazz: object = None) -> dict:
        """filter unexpected dict fields recursively for dataclasses and return"""
        if not isinstance(data, dict):
            return {}
        if not clazz:
            clazz = cls

        new_data = {}
        expected_fields = inspect.signature(clazz).parameters

        for k, v in data.items():
            if k in expected_fields:
                field_type = expected_fields[k].annotation
                if is_dataclass(field_type):
                    v = cls._filter(v, field_type)
                new_data[k] = v
            else:
                logging.warning(f"Skipping unexpected config '{k}' in {clazz.__name__}")

        return new_data
