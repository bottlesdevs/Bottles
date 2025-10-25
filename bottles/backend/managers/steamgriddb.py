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
from typing import Optional

import requests
from requests.exceptions import HTTPError, RequestException

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


class SteamGridDBManager:
    def get_steam_game_asset(
        program_name: str,
        asset_path: str,
        asset_type: Optional[str] = None,
        reraise_exceptions: bool = False,
    ) -> Optional[str]:
        try:
            # url = f"https://steamgrid.usebottles.com/api/search/{program_name}"
            url = f"http://127.0.0.1:8000/api/search/{program_name}"
            if asset_type:
                url = f"{url}/{asset_type}"
            res = requests.get(url, timeout=5)
            res.raise_for_status()
            filename = SteamGridDBManager.__save_asset_to_steam(res.json(), asset_path)

        except Exception as e:
            if isinstance(e, HTTPError):
                logging.warning(str(e))
            else:
                logging.error(str(e))
            if reraise_exceptions:
                raise

        return filename

    @staticmethod
    def __save_asset_to_steam(url: str, asset_path: str) -> str:
        asset_dir = os.path.dirname(asset_path)
        if not os.path.exists(asset_dir):
            os.makedirs(asset_dir)

        res = requests.get(url)
        res.raise_for_status()
        ext = os.path.splitext(url)[-1]
        asset_path += ext
        with open(asset_path, "wb") as img:
            img.write(res.content)

        return os.path.basename(asset_path)
