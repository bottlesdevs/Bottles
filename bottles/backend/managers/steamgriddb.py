# steamgriddb.py
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
import requests

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


class SteamGridDBManager:

    @staticmethod
    def get_game_grid(name: str, config: BottleConfig):
        try:
            url = f"https://steamgrid.usebottles.com/api/search/{name}"
            res = requests.get(url)
        except:
            return

        if res.status_code == 200:
            return SteamGridDBManager.__save_grid(res.json(), config)
    
    @staticmethod
    def get_steam_game_asset(name: str, asset_type: str, config_path: str, base_filename: str):
        try:
            #url = f"https://steamgrid.usebottles.com/api/search/{name}/{asset_type}"
            url = f"http://127.0.0.1:8000/api/search/{name}/{asset_type}"
            print(url)
            res = requests.get(url)
        except:
            return

        if res.status_code == 200:
            assets_path = os.path.join(config_path, "grid")
            return SteamGridDBManager.__save_asset_to_steam(res.json(), assets_path, base_filename)

    @staticmethod
    def __save_grid(url: str, config: BottleConfig):
        grids_path = os.path.join(ManagerUtils.get_bottle_path(config), "grids")
        if not os.path.exists(grids_path):
            os.makedirs(grids_path)

        ext = url.split(".")[-1]
        filename = str(uuid.uuid4()) + "." + ext
        path = os.path.join(grids_path, filename)

        try:
            r = requests.get(url)
            with open(path, "wb") as f:
                f.write(r.content)
        except Exception:
            return
        
        return f"grid:{filename}"
    
    @staticmethod
    def __save_asset_to_steam(url: str, assets_path: str, base_filename: str):
        if not os.path.exists(assets_path):
            os.makedirs(assets_path)

        try:
            r = requests.get(url)
            ext = url.rpartition(".")[-1]
            filename = f"{base_filename}.{ext}"
            path = os.path.join(assets_path, filename)
            with open(path, "wb") as f:
                f.write(r.content)
        except Exception:
            return

        return f"grid:{filename}"
