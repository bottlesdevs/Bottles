from datetime import datetime

from bottles.backend.models.config import BottleConfig


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
    fsr_level: int = 5
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

    def __init__(self, conf: BottleConfig):
        self.name = conf.Name
        self.arch = conf.Arch
        self.path = conf.Path
        self.working_dir = conf.WorkingDir
        self.custom_path = conf.Custom_Path
        self.environment = conf.Environment
        self.dxvk_version = conf.DXVK
        self.vkd3d_version = conf.VKD3D
        self.runner_version = conf.Runner
        self.versioning = conf.Versioning
        self.state = conf.State
        self.dxvk = conf.DXVK
        self.dxvk_nvapi = conf.NVAPI
        self.vkd3d = conf.VKD3D
        self.gamemode = conf.Parameters.gamemode
        self.sync = conf.Parameters.sync
        self.fsr = conf.Parameters.fsr
        self.fsr_level = 5
        # self.aco_compiler = conf.get('aco_compiler', self.aco_compiler)
        self.discrete_gpu = conf.Parameters.discrete_gpu
        self.virtual_desktop = conf.Parameters.virtual_desktop
        self.virtual_desktop_res = conf.Parameters.virtual_desktop_res
        self.pulseaudio_latency = conf.Parameters.pulseaudio_latency
        self.fixme_logs = conf.Parameters.fixme_logs
        self.environment_variables = conf.Environment_Variables
        self.installed_dependencies = conf.Installed_Dependencies
        self.dll_overrides = conf.DLL_Overrides
        self.programs = {}
        self.external_programs = conf.External_Programs
        self.uninstallers = conf.Uninstallers
