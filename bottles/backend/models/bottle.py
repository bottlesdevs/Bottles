from datetime import datetime
from typing import NewType


class Bottle:
    # Details
    name: str = ""
    arch: str = "win64"
    path: str = ""
    working_dir: str = ""
    custom_path: bool = False
    environment: str = ""

    # Components versions
    dxvk_version: str = ""
    vkd3d_version: str = ""
    runner_version: str = ""

    # Date
    creation_date: datetime = None
    update_date: datetime = None

    # Versioning
    versioning: bool = False
    state: int = 0

    # Parameters
    dxvk: bool = False
    dxvk_nvapi: bool = False
    vkd3d: bool = False
    gamemode: bool = False
    sync: str = "wine"
    fsr: bool = False
    fsr_quality_mode: str = "none"
    fsr_sharpening_strength: int = 2
    discrete_gpu: bool = False
    virtual_desktop: bool = False
    virtual_desktop_res: str = "1280x720"
    pulseaudio_latency: bool = False
    fixme_logs: bool = False
    environment_variables: str = ""

    # Data
    installed_dependencies: list = []
    dll_overrides: dict = {}
    programs: dict = {}
    external_programs: dict = {}
    uninstallers: dict = {}

    def __init__(self, conf: dict):
        self.name = conf.get('Name', self.name)
        self.arch = conf.get('Arch', self.arch)
        self.path = conf.get('Path', self.path)
        self.working_dir = conf.get('WorkingDir', self.working_dir)
        self.custom_path = conf.get('Custom_Path', self.custom_path)
        self.environment = conf.get('Environment', self.environment)
        self.dxvk_version = conf.get('DXVK', self.dxvk_version)
        self.vkd3d_version = conf.get('VKD3D', self.vkd3d_version)
        self.runner_version = conf.get('Runner', self.runner_version)
        self.versioning = conf.get('Versioning', self.versioning)
        self.state = conf.get('State', self.state)
        self.dxvk = conf.get('dxvk', self.dxvk)
        self.dxvk_nvapi = conf.get('dxvk_nvapi', self.dxvk_nvapi)
        self.vkd3d = conf.get('vkd3d', self.vkd3d)
        self.gamemode = conf.get('gamemode', self.gamemode)
        self.sync = conf.get('sync', self.sync)
        self.fsr = conf.get('fsr', self.fsr)
        self.fsr_quality_mode = conf.get('fsr_quality_mode', self.fsr_quality_mode)
        self.fsr_sharpening_strength = conf.get('fsr_sharpening_strength', self.fsr_sharpening_strength)
        # self.aco_compiler = conf.get('aco_compiler', self.aco_compiler)
        self.discrete_gpu = conf.get('discrete_gpu', self.discrete_gpu)
        self.virtual_desktop = conf.get('virtual_desktop', self.virtual_desktop)
        self.virtual_desktop_res = conf.get('virtual_desktop_res', self.virtual_desktop_res)
        self.pulseaudio_latency = conf.get('pulseaudio_latency', self.pulseaudio_latency)
        self.fixme_logs = conf.get('fixme_logs', self.fixme_logs)
        self.environment_variables = conf.get('environment_variables', self.environment_variables)
        self.installed_dependencies = conf.get('Installed_Dependencies', self.installed_dependencies)
        self.dll_overrides = conf.get('DLL_Overrides', self.dll_overrides)
        self.programs = conf.get('Programs', self.programs)
        self.external_programs = conf.get('External_Programs', self.external_programs)
        self.uninstallers = conf.get('Uninstallers', self.uninstallers)
