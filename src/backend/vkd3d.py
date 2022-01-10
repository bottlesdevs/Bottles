from .dll import DLLComponent
from .manager_utils import ManagerUtils


class VKD3DComponent(DLLComponent):

    def __init__(self, version:str):
        self.base_path = ManagerUtils.get_vkd3d_path(version)
        self.dlls = {
            "x86": [
                "d3d12.dll"
            ],
            "x64": [
                "d3d12.dll"
            ]
        }
        self.version = version
