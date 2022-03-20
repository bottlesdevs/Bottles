# steam.py
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
import yaml
import shutil
import patoolib
from glob import glob
from pathlib import Path
from functools import lru_cache
from typing import Union, NewType
from datetime import datetime

from bottles.backend.models.samples import Samples  # pyright: reportMissingImports=false
from bottles.backend.globals import Paths
from bottles.backend.utils.steam import SteamUtils
from bottles.backend.logger import Logger

logging = Logger()


class SteamManager:

    @staticmethod
    def __find_steam_path(scope: str = "steamapps") -> Union[str, None]:
        paths = [
            os.path.join(Path.home(), ".local/share/Steam", scope),
            os.path.join(Path.home(), ".var/app/com.valvesoftware.Steam/data/Steam", scope),
        ]
        for path in paths:
            if os.path.isdir(path):
                return path
        return None

    @staticmethod
    def is_steam_supported() -> bool:
        return SteamManager.__find_steam_path() is not None

    @staticmethod
    def get_acf_data(app_id: str) -> Union[dict, None]:
        steam_path = SteamManager.__find_steam_path()
        if steam_path is None:
            return None

        acf_path = f"{steam_path}/appmanifest_{app_id}.acf"
        if not os.path.isfile(acf_path):
            return None

        with open(acf_path, "r") as f:
            data = SteamUtils.parse_acf(f.read())

        return data

    @staticmethod
    def get_runners() -> dict:
        """
        TODO: not used, here for reference or later use
              Bottles get Proton runner from config_info file
        """
        steam_path = SteamManager.__find_steam_path()
        if steam_path is None:
            return {}

        proton_paths = glob(f"{steam_path}/common/Proton -*")
        runners = {}

        for proton_path in proton_paths:
            _name = os.path.basename(proton_path)
            runners[_name] = {
                "path": proton_path
            }

        return runners

    @staticmethod
    def get_runner_path(pfx_path: str) -> Union[tuple, None]:
        """Get runner path from config_info file"""
        config_info = os.path.join(pfx_path, "config_info")

        if not os.path.isfile(config_info):
            return None

        # open file use second line
        with open(config_info, "r") as f:
            lines = f.readlines()
            if len(lines) < 10:
                logging.error(f"{config_info} is not valid, cannot get Steam Proton path")
                return None

            proton_path = lines[2].strip()[:-5]
            proton_name = os.path.basename(proton_path.rsplit("/", 1)[0])

            if not os.path.isdir(proton_path):
                logging.error(f"{proton_path} is not a valid Steam Proton path")
                return None

            return proton_name, proton_path

    @staticmethod
    def list_prefixes() -> dict:
        steam_path = SteamManager.__find_steam_path()

        if steam_path is None:
            return {}

        prefixes = {}
        for path in glob(f"{steam_path}/compatdata/*"):
            if not os.path.isdir(f"{path}/pfx"):
                continue

            _dir_name = os.path.basename(path)
            _acf = SteamManager.get_acf_data(_dir_name)
            _runner = SteamManager.get_runner_path(path)
            _creation_date = datetime.fromtimestamp(os.path.getctime(path)) \
                .strftime("%Y-%m-%d %H:%M:%S.%f")

            if _acf is None or not _acf.get("AppState"):
                logging.warning(f"A Steam prefix was found, but there is no ACF for it: {_dir_name}, skipping...")
                continue

            if _acf["AppState"]["name"] == "Proton Experimental":
                # skip Proton default prefix
                continue

            if _runner is None:
                logging.warning(f"A Steam prefix was found, but there is no Proton for it: {_dir_name}, skipping...")
                continue

            _conf = Samples.config.copy()
            _conf["Name"] = _acf["AppState"]["name"]
            _conf["Environment"] = "Steam"
            _conf["CompatData"] = _dir_name
            _conf["Path"] = os.path.join(path, "pfx")
            _conf["Runner"] = _runner[0]
            _conf["RunnerPath"] = _runner[1]
            _conf["WorkingDir"] = os.path.join(_conf["Path"], "drive_c")
            _conf["Creation_Date"] = _creation_date
            _conf["Update_Date"] = datetime.fromtimestamp(int(_acf["AppState"]["LastUpdated"])) \
                .strftime("%Y-%m-%d %H:%M:%S.%f")

            prefixes[_dir_name] = _conf

        return prefixes

    @staticmethod
    def update_bottles():
        prefixes = SteamManager.list_prefixes()

        for prefix in prefixes.items():
            _name, _conf = prefix
            _bottle = os.path.join(Paths.steam, _conf["CompatData"])

            if os.path.isdir(_bottle):
                logging.warning(f"Bottle for Steam prefix {_conf['CompatData']} already exists, skipping...")
                continue

            logging.info(f"Creating bottle for Steam prefix {_conf['CompatData']}...")
            os.makedirs(_bottle, exist_ok=True)

            with open(os.path.join(_bottle, "config.yml"), "w") as f:
                yaml.dump(_conf, f)

    @staticmethod
    def get_local_config() -> dict:
        steam_path = SteamManager.__find_steam_path("userdata")

        if steam_path is None:
            return {}

        confs = glob(os.path.join(steam_path, "*/config/localconfig.vdf"))
        if len(confs) == 0:
            logging.warning("Could not find any localconfig.vdf files in Steam userdata")
            return {}

        conf_path = confs[0]
        with open(conf_path, "r") as f:
            local_config = SteamUtils.parse_acf(f.read())

        if local_config is None:
            logging.warning(f"Could not parse localconfig.vdf")
            return {}

        return local_config

    @staticmethod
    def get_app_config(prefix: str) -> dict:
        local_config = SteamManager.get_local_config()
        _fail_msg = f"Fail to get app config from Steam for: {prefix}"

        if len(local_config) == 0:
            logging.warning(_fail_msg)
            return {}

        apps = local_config.get("UserLocalConfigStore", {}) \
            .get("Software", {}) \
            .get("Valve", {}) \
            .get("Steam", {}) \
            .get("apps", {})

        if len(apps) == 0 or prefix not in apps:
            logging.warning(_fail_msg)
            return {}

        app_conf = apps[prefix]
        if app_conf is None:
            logging.warning(_fail_msg)
            return {}

        return app_conf
