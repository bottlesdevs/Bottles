# ubisoftconnect.py
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


class UbisoftConnectManager:

    @staticmethod
    def find_conf_path(config: dict) -> Union[str, None]:
        """
        Finds the Ubisoft Connect configurations file path.
        """
        paths = [
            os.path.join(
                ManagerUtils.get_bottle_path(config),
                "drive_c/Program Files (x86)/Ubisoft/Ubisoft Game Launcher/cache/configuration/configurations")
        ]

        for path in paths:
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def is_uconnect_supported(config: dict) -> bool:
        """
        Checks if Ubisoft Connect is supported.
        """
        return UbisoftConnectManager.find_conf_path(config) is not None

    @staticmethod
    def get_installed_games(config: dict) -> list:
        """
        Gets the games.
        """
        found = {}
        games = []
        key = None
        reg_key = "register: HKEY_LOCAL_MACHINE\\SOFTWARE\\Ubisoft\\Launcher\\Installs\\"
        conf_path = UbisoftConnectManager.find_conf_path(config)
        games_path = os.path.join(
                ManagerUtils.get_bottle_path(config),
                "drive_c/Program Files (x86)/Ubisoft/Ubisoft Game Launcher/games")

        if conf_path is None:
            return []

        with open(conf_path, "r", encoding="iso-8859-15") as c:
            for r in c.readlines():
                r = r.strip()

                if r.startswith("- shortcut_name:"):
                    _key = r.replace("- shortcut_name:", "").strip()
                    if _key != "" and _key not in found.keys():
                        key = _key
                        found[key] = None

                elif not key and r.startswith("game_identifier"):
                    _key = r.replace("game_identifier:", "").strip()
                    if _key != "" and _key not in found.keys():
                        key = _key
                        found[key] = None

                elif key and r.startswith(reg_key):
                    appid = r.replace(reg_key, "").replace("\\InstallDir", "").strip()
                    found[key] = appid
                    key, appid = None, None

            for k, v in found.items():
                if not os.path.exists(os.path.join(games_path, k)):
                    continue

                _args = f"uplay://launch/{v}/0"
                _path = "C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\UbisoftConnect.exe"
                _executable = _path.split("\\")[-1]
                _folder = ManagerUtils.get_exe_parent_dir(config, _path)
                games.append({
                    "executable": _path,
                    "arguments": _args,
                    "name": k,
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
