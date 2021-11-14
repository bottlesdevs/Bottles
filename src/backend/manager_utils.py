import subprocess
from typing import NewType
from ..utils import UtilsLogger
from .globals import Paths

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class ManagerUtils:
    '''
    This class contains methods (tools, utilities) that are not
    directly related to the Manager.
    '''

    @staticmethod
    def open_filemanager(
        config: BottleConfig = dict,
        path_type: str = "bottle",
        component: str = "",
        custom_path: str = ""
    ) -> bool:
        logging.info("Opening the file manager in the path …")

        if path_type == "bottle":
            bottle_path = ManagerUtils.get_bottle_path(config)
            path = f"{bottle_path}/drive_c"

        if component != "":
            if path_type in ["runner", "runner:proton"]:
                path = ManagerUtils.get_runner_path(component)

            if path_type == "dxvk":
                path = ManagerUtils.get_dxvk_path(component)

            if path_type == "vkd3d":
                path = ManagerUtils.get_vkd3d_path(component)

            if path_type == "nvapi":
                path = ManagerUtils.get_nvapi_path(component)

        if path_type == "custom" and custom_path != "":
            path = custom_path

        command = f"xdg-open '{path}'"
        return subprocess.Popen(command, shell=True).communicate()

    @staticmethod
    def get_bottle_path(config: BottleConfig) -> str:
        if config.get("Custom_Path"):
            return config.get("Path")
        return f"{Paths.bottles}/{config.get('Path')}"

    @staticmethod
    def get_runner_path(runner: str) -> str:
        return f"{Paths.runners}/{runner}"

    @staticmethod
    def get_dxvk_path(dxvk: str) -> str:
        return f"{Paths.dxvk}/{dxvk}"

    @staticmethod
    def get_vkd3d_path(vkd3d: str) -> str:
        return f"{Paths.vkd3d}/{vkd3d}"

    @staticmethod
    def get_nvapi_path(nvapi: str) -> str:
        return f"{Paths.nvapi}/{nvapi}"
