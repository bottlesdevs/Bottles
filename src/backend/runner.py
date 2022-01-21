# runner.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
import os
import time
import shutil
import subprocess
from typing import NewType

from bottles.utils import UtilsTerminal, UtilsLogger, RunAsync, detect_encoding # pyright: reportMissingImports=false
from bottles.backend.globals import Paths, CMDSettings, gamemode_available, gamescope_available
from bottles.backend.manager_utils import ManagerUtils
from bottles.backend.runtime import RuntimeManager
from bottles.backend.display import DisplayUtils
from bottles.backend.gpu import GPUUtils
from bottles.backend.result import Result
from bottles.backend.wine.catalogs import win_versions
from bottles.backend.wine.winecommand import WineCommand
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.wine.reg import Reg

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class Runner:
    '''
    This class handle everything related to the runner (e.g. WINE, Proton).
    It should not contain any manager logic (e.g. catalogs, checks, etc.) or
    any bottle related stuff (e.g. config handling, etc.), also DXVK, VKD3D,
    NVAPI handling should not performed from here. This class should be kept
    as clean as possible to easily migrate to the libwine in the future.
    <https://github.com/bottlesdevs/libwine>
    '''

    @staticmethod
    def run_lnk(
        config: BottleConfig,
        file_path: str,
        arguments: str = "",
        environment: dict = False
    ):
        '''
        Run a .lnk file with arguments and environment variables, inside
        a bottle using the config provided.
        '''
        logging.info("Running link file on the bottle…")

        command = f"start /unix '{file_path}'"
        winecmd = WineCommand(
            config=config, 
            command=f"start /unix '{file_path}'", 
            arguments=arguments, 
            environment=environment
        )
        RunAsync(winecmd.run)

    @staticmethod
    def run_executable(
        config: BottleConfig,
        file_path: str,
        arguments: str = "",
        environment: dict = False,
        no_async: bool = False,
        cwd: str = None,
        move_file: bool = False,
        move_progress: callable = None,
        terminal: bool = False
    ):
        '''
        Run an executable file with arguments and environment variables, inside
        a bottle using the config provided.
        '''
        logging.info("Running an executable on the bottle…")

        if file_path in [None, ""]:
            logging.error("No executable file path provided.")
            return False

        if move_file:
            new_path = ManagerUtils.move_file_to_bottle(
                file_path=file_path,
                config=config,
                fn_update=move_progress
            )
            if new_path:
                file_path = new_path

        command = f"'{file_path}'"

        if "msi" in file_path.split("."):
            command = f"msiexec /i '{file_path}'"
        elif "bat" in file_path.split("."):
            command = f"wineconsole cmd /c '{file_path}'"

        winecmd = WineCommand(
            config=config, 
            command=command,
            arguments=arguments, 
            environment=environment, 
            comunicate=True, 
            cwd=cwd,
            terminal=terminal
        )
        if no_async:
            winecmd.run()
            return Result(status=True)
        else:
            RunAsync(winecmd.run)

    @staticmethod
    def run_layer_executable(config: BottleConfig, layer: dict):
        '''
        Run a layer executable.
        '''
        WineCommand(
            config=config,
            file_path=layer["exec_path"],
            arguments=layer["exec_args"],
            environment=layer["exec_env"],
            no_async=True
        ).run()

    @staticmethod
    def set_windows(config: BottleConfig, version: str):
        '''
        Change Windows version in a bottle from the given
        configuration.
        ----------
        supported versions:
            - win10 (Microsoft Windows 10)
            - win81 (Microsoft Windows 8.1)
            - win8 (Microsoft Windows 8)
            - win7 (Microsoft Windows 7)
            - win2008r2 (Microsoft Windows 2008 R1)
            - win2008 (Microsoft Windows 2008)
            - winxp (Microsoft Windows XP)
        ------
        raises: ValueError
            If the given version is invalid.
        '''
        if version not in win_versions:
            raise ValueError("Given version is not supported.")
            
        if version == "winxp" and config.get("Arch") == "win64":
            version = "winxp64"

        reg = Reg(config)
        wineboot = WineBoot(config)
        del_keys = {
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion": "SubVersionNumber",
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion": "VersionNumber",
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion": "CSDVersion",
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion": "CurrentBuildNumber",
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion": "CurrentVersion",
            "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\ProductOptions": "ProductType",
            "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\ServiceCurrent": "OS",
            "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\Windows": "CSDVersion",
            "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\ProductOptions": "ProductType",
            "HKEY_CURRENT_USER\\Softwarw\\Wine": "Version"
        }
        for d in del_keys:
            reg.remove(d, del_keys[d])
            
        reg.add(
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion",
            value="CSDVersion",
            data=win_versions.get(version)["CSDVersion"]
        )

        reg.add(
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion",
            value="CurrentBuildNumber",
            data=win_versions.get(version)["CurrentBuildNumber"]
        )

        reg.add(
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion",
            value="CurrentVersion",
            data=win_versions.get(version)["CurrentVersion"]
        )

        if "ProductType" in win_versions.get(version):
            '''windows xp 32 doesn't have ProductOptions/ProductType key'''
            reg.add(
                key="HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\ProductOptions",
                value="ProductType",
                data=win_versions.get(version)["ProductType"]
            )

        reg.add(
            key="HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\Windows",
            value="CSDVersion",
            data=win_versions.get(version)["CSDVersionHex"],
            keyType="REG_DWORD"
        )

        wineboot.restart()
    
    @staticmethod
    def set_app_default(config: BottleConfig, version: str, executable: str):
        '''
        Change default Windows version per application in a bottle
        from the given configuration.
        ----------
        supported versions:
            - win10 (Microsoft Windows 10)
            - win81 (Microsoft Windows 8.1)
            - win8 (Microsoft Windows 8)
            - win7 (Microsoft Windows 7)
            - win2008r2 (Microsoft Windows 2008 R1)
            - win2008 (Microsoft Windows 2008)
            - winxp (Microsoft Windows XP)
        ------
        raises: ValueError
            If the given version is invalid.
        '''
        if version not in win_versions:
            raise ValueError("Given version is not supported.")
            
        if version == "winxp" and config.get("Arch") == "win64":
            version = "winxp64"
        
        reg = Reg(config)
            
        reg.add(
            key=f"HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\{executable}",
            value="Version",
            data=version
        )

    @staticmethod
    def toggle_virtual_desktop(
        config: BottleConfig,
        state: bool,
        resolution: str = "800x600"
    ):
        '''
        This function toggles the virtual desktop for a bottle, updating
        the Desktops registry key.
        '''
        wineboot = WineBoot(config)
        reg = Reg(config)

        if state:
            reg.add(
                key="HKEY_CURRENT_USER\\Software\\Wine\\Explorer",
                value="Desktop",
                data="Default"
            )
            reg.add(
                key="HKEY_CURRENT_USER\\Software\\Wine\\Explorer\\Desktops",
                value="Default",
                data=resolution
            )
        else:
            reg.remove(
                key="HKEY_CURRENT_USER\\Software\\Wine\\Explorer",
                value="Desktop"
            )
        wineboot.update()
    
    @staticmethod
    def runner_update(config:BottleConfig, manager:object):
        '''
        This method should be executed after changing the runner
        for a bottle. It do a prefix update and re-initialize the
        active DLLComponents (dxvk, dxvk-nvapi, vkd3d..).
        '''
        logging.info(f"Doing runner update for bottle: {config['Name']}")
        wineboot = WineBoot(config)

        # perform a prefix update
        wineboot.update()
        # kill wineserver after update
        wineboot.kill()
        
        if config["Parameters"]["dxvk"]:
            manager.install_dll_component(config, "dxvk", overrides_only=True)
        if config["Parameters"]["dxvk_nvapi"]:
            manager.install_dll_component(config, "nvapi", overrides_only=True)
        if config["Parameters"]["vkd3d"]:
            manager.install_dll_component(config, "vkd3d", overrides_only=True)
        
        return Result(status=True)

    @staticmethod
    def apply_cmd_settings(config:BottleConfig, scheme:dict={}):
        '''
        Change settings for the wine command line in a bottle.
        This method can also be used to apply the default settings, part
        of the Bottles experience, these are meant to improve the
        readability and usability.
        '''
        reg = Reg(config)

        for key, value in CMDSettings.items():
            if key not in scheme:
                scheme[key] = value

        for key, value in scheme.items():
            keyType="REG_DWORD"

            if key == "FaceName":
                keyType="REG_SZ"

            reg.add(
                key="HKEY_CURRENT_USER\\Console\\C:_windows_system32_wineconsole.exe",
                value=key,
                data=value,
                keyType=keyType
            )
        
