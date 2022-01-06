import gi
import os
import subprocess
from typing import NewType, Union
from datetime import datetime
from gi.repository import GLib

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
    def get_layer_path(layer: str) -> str:
        return f"{Paths.layers}/{layer}"

    @staticmethod
    def get_bottle_path(config: BottleConfig) -> str:
        if "IsLayer" in config.keys():
            return ManagerUtils.get_layer_path(config["Path"])
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

    @staticmethod
    def move_file_to_bottle(
        file_path: str, 
        config: BottleConfig,
        fn_update: callable = None
    ) -> Union[str, bool]:
        logging.info(f"Adding file {file_path} to the bottle …")
        bottle_path = ManagerUtils.get_bottle_path(config)
        
        if not os.path.exists(f"{bottle_path}/storage"):
            '''
            If the storage folder does not exist for the bottle,
            create it before moving the file.
            '''
            os.makedirs(f"{bottle_path}/storage")
        
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_new_path = f"{bottle_path}/storage/{file_name}"

        logging.info(f"Copying file {file_path} to the bottle …")
        try:
            with open(file_path, "rb") as f_in:
                with open(file_new_path, "wb") as f_out:
                    for i in range(file_size):
                        f_out.write(f_in.read(1))
                        _size = i / file_size
                        
                        if fn_update:
                            if _size % 0.1 == 0:
                                GLib.idle_add(fn_update, _size)
                    GLib.idle_add(fn_update, 1)
            return file_new_path
        except:
            logging.error(f"Could not copy file {file_path} to the bottle.")
            return False

    @staticmethod
    def create_desktop_entry(config, program: dict):
        if "FLATPAK_ID" in os.environ:
            return None

        desktop_file = "%s/%s--%s--%s.desktop" % (
            Paths.applications,
            config.get('Name'),
            program.get("name"),
            datetime.now().timestamp()
        )

        with open(desktop_file, "w") as f:
            f.write(f"[Desktop Entry]\n")
            f.write(f"Name={program.get('name')}\n")
            f.write(f"Exec=bottles -e '{program.get('executable')}' -b '{config.get('Name')}'\n")
            f.write(f"Type=Application\n")
            f.write(f"Terminal=false\n")
            f.write(f"Categories=Application;\n")
            f.write(f"Icon=com.usebottles.bottles-program\n")
            f.write(f"Comment=Launch {program.get('name')} using Bottles.\n")
            # Actions
            f.write("Actions=Configure;\n")
            f.write("[Desktop Action Configure]\n")
            f.write("Name=Configure in Bottles\n")
            f.write(f"Exec=bottles -b '{config.get('Name')}'\n")

    @staticmethod
    def browse_wineprefix(wineprefix: dict) -> bool:
        '''
        This function popup the system file manager to browse
        the wineprefix path.
        '''
        return ManagerUtils.open_filemanager(
            path_type="custom",
            custom_path=wineprefix.get("Path")
        )