from bottles.backend.dlls.dll import DLLComponent
from bottles.backend.utils.manager import ManagerUtils


class D8VKComponent(DLLComponent):
    dlls = {
        "x32": [
            "d3d8.dll"
        ]
    }

    @staticmethod
    def get_base_path(version: str):
        return ManagerUtils.get_d8vk_path(version)
