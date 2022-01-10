from .dll import DLLComponent
from .manager_utils import ManagerUtils


class DXVKComponent(DLLComponent):

    def __init__(self, version:str):
        self.base_path = ManagerUtils.get_dxvk_path(version)
        self.dlls = {
            "x32": [
                "d3d9.dll",
                "d3d10.dll",
                "d3d10_1.dll",
                "d3d10core.dll",
                "d3d11.dll",
                "dxgi.dll"
            ],
            "x64": [
                "d3d9.dll",
                "d3d10.dll",
                "d3d10_1.dll",
                "d3d10core.dll",
                "d3d11.dll",
                "dxgi.dll"
            ]
        }
        self.version = version
