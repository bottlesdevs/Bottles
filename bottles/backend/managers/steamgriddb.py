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
from functools import lru_cache

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


class SteamGridDBManager:
    
    @staticmethod
    def get_game_grid(name: str, config: dict):
        try:
            res = requests.get(f"https://steamgrid.usebottles.com/api/search/{name}")
        except:
            return
            
        if res.status_code == 200:
            return SteamGridDBManager.__save_grid(res.json(), config)

    def __save_grid(url: str, config: dict):
        grids_path = os.path.join(ManagerUtils.get_bottle_path(config), 'grids')
        if not os.path.exists(grids_path):
            os.makedirs(grids_path)
            
        ext = url.split('.')[-1]
        filename = str(uuid.uuid4()) + '.' + ext
        path = os.path.join(grids_path, filename)

        try:
            r = requests.get(url)
            with open(path, 'wb') as f:
                f.write(r.content)
        except Exception as e:
            return

        return f"grid:{filename}"