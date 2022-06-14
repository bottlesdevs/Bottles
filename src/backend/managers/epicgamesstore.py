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

        if path is not None:
            for file in os.listdir(path):
                if file.endswith(".item"):
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

