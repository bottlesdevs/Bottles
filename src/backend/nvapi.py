from .dll import DLLComponent
from .manager_utils import ManagerUtils


class NVAPIComponent(DLLComponent):

    def __init__(self, version:str):
        self.base_path = ManagerUtils.get_nvapi_path(version)
        self.dlls = {
            "x32": [
                "nvapi.dll"
            ],
            "x64": [
                "nvapi64.dll"
            ]
        }
        self.version = version
