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

import shlex
from typing import NewType

from bottles.utils import UtilsLogger, RunAsync # pyright: reportMissingImports=false
from bottles.backend.globals import CMDSettings, gamemode_available, gamescope_available
from bottles.backend.manager_utils import ManagerUtils
from bottles.backend.result import Result
from bottles.backend.wine.catalogs import win_versions
from bottles.backend.wine.winecommand import WineCommand
from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.wine.wineserver import WineServer
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
            
        bundle = {
            "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion": [
                {
                    "value": "CSDVersion",
                    "data": win_versions.get(version)["CSDVersion"]
                },
                {
                    "value": "CurrentBuild",
                    "data": win_versions.get(version)["CurrentBuild"]
                },
                {
                    "value": "CurrentBuildNumber",
                    "data": win_versions.get(version)["CurrentBuildNumber"]
                },
                {
                    "value": "CurrentVersion",
                    "data": win_versions.get(version)["CurrentVersion"]
                },
                {
                    "value": "ProductName",
                    "data": win_versions.get(version)["ProductName"]
                },
                {
                    "value": "CurrentMinorVersionNumber",
                    "data": win_versions.get(version)["CurrentMinorVersionNumber"],
                    "keyType": "dword"
                },
                {
                    "value": "CurrentMajorVersionNumber",
                    "data": win_versions.get(version)["CurrentMajorVersionNumber"],
                    "keyType": "dword"
                },
            ]
        }

        if config.get("Arch") == "win64":
            bundle["HKEY_LOCAL_MACHINE\\Software\\Wow6432Node\\Microsoft\\Windows NT\\CurrentVersion"] = [
                {
                    "value": "CSDVersion",
                    "data": win_versions.get(version)["CSDVersion"]
                },
                {
                    "value": "CurrentBuild",
                    "data": win_versions.get(version)["CurrentBuild"]
                },
                {
                    "value": "CurrentBuildNumber",
                    "data": win_versions.get(version)["CurrentBuildNumber"]
                },
                {
                    "value": "CurrentVersion",
                    "data": win_versions.get(version)["CurrentVersion"]
                },
                {
                    "value": "ProductName",
                    "data": win_versions.get(version)["ProductName"]
                },
                {
                    "value": "CurrentMinorVersionNumber",
                    "data": win_versions.get(version)["CurrentMinorVersionNumber"],
                    "keyType": "dword"
                },
                {
                    "value": "CurrentMajorVersionNumber",
                    "data": win_versions.get(version)["CurrentMajorVersionNumber"],
                    "keyType": "dword"
                },
            ]

        if "ProductType" in win_versions.get(version):
            '''windows xp 32 doesn't have ProductOptions/ProductType key'''
            bundle["HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\ProductOptions"] = [
                {
                    "value": "ProductType",
                    "data": win_versions.get(version)["ProductType"]
                }
            ]

        reg.import_bundle(bundle)

        wineboot.restart()
        wineboot.update()
    
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
