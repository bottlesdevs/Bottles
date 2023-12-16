# ubisoftconnect.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import uuid
from typing import Union, Optional

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils


class UbisoftConnectManager:

    @staticmethod
    def find_conf_path(config: BottleConfig) -> Union[str, None]:
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
    def is_uconnect_supported(config: BottleConfig) -> bool:
        """
        Checks if Ubisoft Connect is supported.
        """
        return UbisoftConnectManager.find_conf_path(config) is not None

    # noinspection PyTypeChecker
    @staticmethod
    def get_installed_games(config: BottleConfig) -> list:
        """
        Gets the games.
        """
        found = {}
        games = []
        key: Optional[str] = None
        appid: Optional[str] = None
        thumb: Optional[str] = None
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

                if r.startswith("name:"):
                    _key = r.replace("name:", "").strip()
                    if _key != "" and _key not in found.keys():
                        key = _key
                        found[key] = {
                            "name": None,
                            "appid": None,
                            "thumb_image": None
                        }

                elif key and r.startswith("- shortcut_name:"):
                    _name = r.replace("- shortcut_name:", "").strip()
                    if _name != "":
                        name = _name
                        found[key]["name"] = name

                elif key and found[key]["name"] is None and r.startswith("display_name:"):
                    name = r.replace("display_name:", "").strip()
                    found[key]["name"] = name

                elif key and r.startswith("thumb_image:"):
                    thumb = r.replace("thumb_image:", "").strip()
                    found[key]["thumb_image"] = thumb

                elif key and r.startswith(reg_key):
                    appid = r.replace(reg_key, "").replace("\\InstallDir", "").strip()
                    found[key]["appid"] = appid

                if None not in [key, appid, thumb]:
                    key, name, appid, thumb = None, None, None, None

            for k, v in found.items():
                if v["name"] is None or not os.path.exists(os.path.join(games_path, v["name"])):
                    continue

                _args = f"uplay://launch/{v['appid']}/0"
                _path = "C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\UbisoftConnect.exe"
                _executable = _path.split("\\")[-1]
                _folder = ManagerUtils.get_exe_parent_dir(config, _path)
                _thumb = "" if v['thumb_image'] is None else f"ubisoft:{v['thumb_image']}"
                games.append({
                    "executable": _path,
                    "arguments": _args,
                    "name": v["name"],
                    "thumb": _thumb,
                    "path": _path,
                    "folder": _folder,
                    "icon": "com.usebottles.bottles-program",
                    "id": str(uuid.uuid4()),
                })
        return games
