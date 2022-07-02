# epicgamesstore.py
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

import os
import uuid
import json
from typing import Union, NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils


class EpicGamesStoreManager:

    @staticmethod
    def find_games_path(config: dict) -> Union[str, None]:
        """
        Finds the Epic Games path.
        """
        paths = [
            os.path.join(
                ManagerUtils.get_bottle_path(config),
                "drive_c/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")
        ]

        for path in paths:
            if os.path.isdir(path):
                return path
        return None

    @staticmethod
    def is_epic_supported(config: dict) -> bool:
        """
        Checks if Epic Games is supported.
        """
        return EpicGamesStoreManager.find_games_path(config) is not None

    @staticmethod
    def get_installed_games(config: dict) -> list:
        """
        Gets the games.
        """
        games = []
        path = EpicGamesStoreManager.find_games_path(config)

        if path is None:
            return []

        for file in os.listdir(path):
            if not file.endswith(".item"):
                continue

            with open(os.path.join(path, file), "r") as f:
                data = json.load(f)
                _path = f"{data['InstallLocation']}/{data['LaunchExecutable']}"
                _executable = _path.split("\\")[-1]
                _folder = ManagerUtils.get_exe_parent_dir(config, _path)
                games.append({
                    "executable": _executable,
                    "arguments": "",
                    "name": data["DisplayName"],
                    "path": _path,
                    "folder": _folder,
                    "icon": "com.usebottles.bottles-program",
                    "dxvk": config["Parameters"]["dxvk"],
                    "vkd3d": config["Parameters"]["vkd3d"],
                    "dxvk_nvapi": config["Parameters"]["dxvk_nvapi"],
                    "id": uuid.uuid4(),
                })
        return games

    '''
    TODO: the following code is conceptually correct, it read the dat file which
          lists all the installed games, then generate a new entry using the
          -com.epicgames.launcher:// protocol and the AppName, but it doesn't
          works for some reason. I was unable to make it works on other prefix
          managers and seems like it's a bug in the Epic Games Launcher. Keeping
          this disabled until I find a solution or the bug is fixed.
    @staticmethod
    def find_dat_path(config: dict) -> Union[str, None]:
        """
        Finds the Epic Games dat file path.
        """
        paths = [
            os.path.join(
                ManagerUtils.get_bottle_path(config),
                "drive_c/ProgramData/Epic/UnrealEngineLauncher")
        ]

        for path in paths:
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def is_epic_supported(config: dict) -> bool:
        """
        Checks if Epic Games is supported.
        """
        return EpicGamesStoreManager.find_dat_path(config) is not None

    @staticmethod
    def get_installed_games(config: dict) -> list:
        """
        Gets the games.
        """
        games = []
        dat_path = EpicGamesStoreManager.find_dat_path(config)

        if dat_path is None:
            return []

        with open(os.path.join(dat_path, "LauncherInstalled.dat"), "r") as dat:
            data = json.load(dat)

            for game in data["InstallationList"]:
                _uri = f"-com.epicgames.launcher://apps/{game['AppName']}?action=launch&silent=true"
                _args = f"-opengl -SkipBuildPatchPrereq {_uri}"
                _name = game["InstallLocation"].split("\\")[-1]
                _path = "C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win32\\" \
                        "EpicGamesLauncher.exe"
                _executable = _path.split("\\")[-1]
                _folder = ManagerUtils.get_exe_parent_dir(config, _path)
                games.append({
                    "executable": _path,
                    "arguments": _args,
                    "name": _name,
                    "path": _path,
                    "folder": _folder,
                    "icon": "com.usebottles.bottles-program",
                    "dxvk": config["Parameters"]["dxvk"],
                    "vkd3d": config["Parameters"]["vkd3d"],
                    "dxvk_nvapi": config["Parameters"]["dxvk_nvapi"],
                    "fsr": config["Parameters"]["fsr"],
                    "virtual_desktop": config["Parameters"]["virtual_desktop"],
                    "pulseaudio_latency": config["Parameters"]["pulseaudio_latency"],
                    "id": str(uuid.uuid4()),
                })
        return games
        '''
