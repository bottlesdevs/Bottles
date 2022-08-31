# steam.py
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
from bottles.backend.utils import yaml
import shlex
import shutil
import subprocess
import contextlib
from glob import glob
from pathlib import Path
from functools import lru_cache
from typing import Union, NewType
from datetime import datetime

from bottles.backend.models.samples import Samples  # pyright: reportMissingImports=false
from bottles.backend.models.result import Result
from bottles.backend.wine.winecommand import WineCommand
from bottles.backend.globals import Paths
from bottles.backend.utils.steam import SteamUtils
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils import vdf
from bottles.backend.logger import Logger

logging = Logger()


class SteamManager:
    steamapps_path = None
    userdata_path = None
    localconfig_path = None
    localconfig = {}
    library_folders = []

    def __init__(self, config: dict = None, is_windows: bool = False, check_only: bool = False):
        self.config = config
        self.is_windows = is_windows
        self.steam_path = self.__find_steam_path()
        self.is_steam_supported = self.steam_path is not None
        if self.is_steam_supported and not check_only:
            self.steamapps_path = self.__get_scoped_path("steamapps")
            self.userdata_path = self.__get_scoped_path("userdata")
            self.localconfig_path = self.__get_local_config_path()
            self.localconfig = self.__get_local_config()
            self.library_folders = self.__get_library_folders()

    def __find_steam_path(self) -> Union[str, None]:
        if self.is_windows and self.config:
            paths = [os.path.join(ManagerUtils.get_bottle_path(self.config), "drive_c/Program Files (x86)/Steam")]
        else:
            paths = [
                os.path.join(Path.home(), ".var/app/com.valvesoftware.Steam/data/Steam"),
                os.path.join(Path.home(), ".local/share/Steam"),
                os.path.join(Path.home(), ".steam/debian-installation"),
                os.path.join(Path.home(), ".steam"),
            ]

        for path in paths:
            if os.path.isdir(path):
                return path

    def __get_scoped_path(self, scope: str = "steamapps"):
        """scopes: steamapps, userdata"""
        if scope not in ["steamapps", "userdata"]:
            raise ValueError("scope must be either 'steamapps' or 'userdata'")

        path = os.path.join(self.steam_path, scope)
        if os.path.isdir(path):
            return path

    @staticmethod
    def get_acf_data(libraryfolder: str, app_id: str) -> Union[dict, None]:
        acf_path = os.path.join(libraryfolder, f"steamapps/appmanifest_{app_id}.acf")
        if not os.path.isfile(acf_path):
            return

        with open(acf_path, "r") as f:
            data = SteamUtils.parse_acf(f.read())

        return data

    def __get_local_config_path(self) -> Union[str, None]:
        if self.userdata_path is None:
            return None

        confs = glob(os.path.join(self.userdata_path, "*/config/localconfig.vdf"))
        if len(confs) == 0:
            logging.warning("Could not find any localconfig.vdf file in Steam userdata")
            return

        return confs[0]

    def __get_library_folders(self) -> Union[list, None]:
        if not self.steamapps_path:
            return

        library_folders_path = os.path.join(self.steamapps_path, "libraryfolders.vdf")
        library_folders = []

        if not os.path.exists(library_folders_path):
            logging.warning("Could not find the libraryfolders.vdf file")
            return

        with open(library_folders_path, "r") as f:
            _library_folders = SteamUtils.parse_acf(f.read())

        if _library_folders is None or not _library_folders.get("libraryfolders"):
            logging.warning(f"Could not parse libraryfolders.vdf")
            return

        for _, folder in _library_folders["libraryfolders"].items():
            if not isinstance(folder, dict) \
                    or not folder.get("path") \
                    or not folder.get("apps"):
                continue

            library_folders.append(folder)

        return library_folders if len(library_folders) > 0 else None

    @lru_cache
    def get_appid_library_path(self, appid: str) -> Union[str, None]:
        if self.library_folders is None:
            return

        for folder in self.library_folders:
            if appid in folder["apps"].keys():
                return folder["path"]

    def __get_local_config(self) -> dict:
        if self.localconfig_path is None:
            return {}

        with open(self.localconfig_path, "r") as f:
            data = SteamUtils.parse_acf(f.read())

        if data is None:
            logging.warning(f"Could not parse localconfig.vdf")
            return {}

        return data

    def save_local_config(self, new_data: dict):
        if self.localconfig_path is None:
            return

        if os.path.isfile(self.localconfig_path):
            now = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            shutil.copy(self.localconfig_path, f"{self.localconfig_path}.bck.{now}")

        with open(self.localconfig_path, "w") as f:
            SteamUtils.to_vdf(new_data, f)

        logging.info(f"Steam config saved")

    @staticmethod
    @lru_cache
    def get_runner_path(pfx_path: str) -> Union[tuple, None]:
        """Get runner path from config_info file"""
        config_info = os.path.join(pfx_path, "config_info")

        if not os.path.isfile(config_info):
            return None

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

    def list_apps_ids(self) -> list:
        """List all apps in Steam"""
        apps = self.localconfig.get("UserLocalConfigStore", {}) \
            .get("Software", {}) \
            .get("Valve", {}) \
            .get("Steam", {})
        apps = apps.get("apps") if apps.get("apps") else apps.get("Apps")
        if apps is None:
            return []
        return apps

    def get_installed_apps_as_programs(self) -> list:
        """This is a Steam for Windows only function"""
        if not self.is_windows:
            raise NotImplementedError("This function is only implemented for Windows versions of Steam")

        apps_ids = self.list_apps_ids()
        apps = []

        if len(apps_ids) == 0:
            return []

        for app_id in apps_ids:
            _acf = self.get_acf_data(self.steam_path, app_id)
            if _acf is None:
                continue

            _path = _acf["AppState"].get("LauncherPath", "C:\\Program Files (x86)\\Steam\\steam.exe")
            _executable = _path.split("\\")[-1]
            _folder = ManagerUtils.get_exe_parent_dir(self.config, _path)
            apps.append({
                "executable": _executable,
                "arguments": f"steam://run/{app_id}",
                "name": _acf["AppState"]["name"],
                "path": _path,
                "folder": _folder,
                "icon": "com.usebottles.bottles-program",
                "dxvk": self.config["Parameters"]["dxvk"],
                "vkd3d": self.config["Parameters"]["vkd3d"],
                "dxvk_nvapi": self.config["Parameters"]["dxvk_nvapi"],
                "fsr": self.config["Parameters"]["fsr"],
                "virtual_desktop": self.config["Parameters"]["virtual_desktop"],
                "pulseaudio_latency": self.config["Parameters"]["pulseaudio_latency"],
                "id": str(uuid.uuid4()),
            })

        return apps

    def list_prefixes(self) -> dict:
        apps = self.list_apps_ids()
        prefixes = {}

        if len(apps) == 0:
            return {}

        for appid, appdata in apps.items():
            _library_path = self.get_appid_library_path(appid)
            if _library_path is None:
                continue

            _path = os.path.join(_library_path, "steamapps/compatdata", appid)

            if not os.path.isdir(os.path.join(_path, "pfx")):
                logging.debug(f"{appid} does not contain a prefix")
                continue

            _launch_options = self.get_launch_options(appid, appdata)
            _dir_name = os.path.basename(_path)
            _acf = self.get_acf_data(_library_path, _dir_name)
            _runner = self.get_runner_path(_path)
            _creation_date = datetime.fromtimestamp(os.path.getctime(_path)) \
                .strftime("%Y-%m-%d %H:%M:%S.%f")

            if _acf is None or not _acf.get("AppState"):
                logging.warning(f"A Steam prefix was found, but there is no ACF for it: {_dir_name}, skipping…")
                continue

            if "Proton" in _acf["AppState"]["name"]:
                # skip Proton default prefix
                continue

            if _runner is None:
                logging.warning(f"A Steam prefix was found, but there is no Proton for it: {_dir_name}, skipping…")
                continue

            _conf = Samples.config.copy()
            _conf["Name"] = _acf["AppState"]["name"]
            _conf["Environment"] = "Steam"
            _conf["CompatData"] = _dir_name
            _conf["Path"] = os.path.join(_path, "pfx")
            _conf["Runner"] = _runner[0]
            _conf["RunnerPath"] = _runner[1]
            _conf["WorkingDir"] = os.path.join(_conf["Path"], "drive_c")
            _conf["Creation_Date"] = _creation_date
            _conf["Update_Date"] = datetime.fromtimestamp(int(_acf["AppState"]["LastUpdated"])) \
                .strftime("%Y-%m-%d %H:%M:%S.%f")

            # Launch options
            _conf["Parameters"]["mangohud"] = "mangohud" in _launch_options["command"]
            _conf["Parameters"]["gamemode"] = "gamemode" in _launch_options["command"]
            _conf["Environment_Variables"] = _launch_options["env_vars"]
            for p in _launch_options["env_params"]:
                _conf["Parameters"][p] = _launch_options["env_params"][p]

            prefixes[_dir_name] = _conf

        return prefixes

    def update_bottles(self):
        prefixes = self.list_prefixes()

        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(Paths.steam)  # generate new configs at start

        for prefix in prefixes.items():
            _name, _conf = prefix
            _bottle = os.path.join(Paths.steam, _conf["CompatData"])

            os.makedirs(_bottle, exist_ok=True)

            with open(os.path.join(_bottle, "bottle.yml"), "w") as f:
                yaml.dump(_conf, f)

    def get_app_config(self, prefix: str) -> dict:
        _fail_msg = f"Fail to get app config from Steam for: {prefix}"

        if len(self.localconfig) == 0:
            logging.warning(_fail_msg)
            return {}

        apps = self.localconfig.get("UserLocalConfigStore", {}) \
            .get("Software", {}) \
            .get("Valve", {}) \
            .get("Steam", {})
        apps = apps.get("apps") if apps.get("apps") else apps.get("Apps")

        if len(apps) == 0 or prefix not in apps:
            logging.warning(_fail_msg)
            return {}

        return apps[prefix]

    def get_launch_options(self, prefix: str, app_conf: dict = None) -> {}:
        if app_conf is None:
            app_conf = self.get_app_config(prefix)

        launch_options = app_conf.get("LaunchOptions", "")
        _fail_msg = f"Fail to get launch options from Steam for: {prefix}"
        prefix, args = "", ""
        env_vars = {}
        res = {
            "command": "",
            "args": "",
            "env_vars": {},
            "env_params": {}
        }

        if len(launch_options) == 0:
            logging.debug(_fail_msg)
            return res

        if "%command%" in launch_options:
            _c = launch_options.split("%command%")
            prefix = _c[0] if len(_c) > 0 else ""
            args = _c[1] if len(_c) > 1 else ""
        else:
            args = launch_options

        try:
            prefix = shlex.split(prefix.strip())
        except ValueError:
            prefix = prefix.split(shlex.quote(prefix.strip()))

        for p in prefix.copy():
            if "=" in p:
                k, v = p.split("=", 1)
                v = shlex.quote(v) if " " in v else v
                env_vars[k] = v
                prefix.remove(p)

        command = " ".join(prefix)
        res = {
            "command": command,
            "args": args,
            "env_vars": env_vars,
            "env_params": {}
        }
        tmp_env_vars = res["env_vars"].copy()

        for e in tmp_env_vars:
            if e in Samples.bottles_to_steam_relations:
                k, v = Samples.bottles_to_steam_relations[e]
                if v is None:
                    v = tmp_env_vars[e]
                res["env_params"][k] = v
                del res["env_vars"][e]

        return res

    # noinspection PyTypeChecker
    def set_launch_options(self, prefix: str, options: dict):
        original_launch_options = self.get_launch_options(prefix)
        _fail_msg = f"Fail to set launch options for: {prefix}"

        if 0 in [len(self.localconfig), len(original_launch_options)]:
            logging.warning(_fail_msg)
            return

        command = options.get("command", "")
        env_vars = options.get("env_vars", {})

        if len(env_vars) > 0:
            for k, v in env_vars.items():
                v = shlex.quote(v) if " " in v else v
                original_launch_options["env_vars"][k] = v

        launch_options = ""

        for e, v in original_launch_options["env_vars"].items():
            launch_options += f"{e}={v} "
        launch_options += f"{command} %command% {original_launch_options['args']}"

        try:
            self.localconfig["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]["apps"][prefix]["LaunchOptions"] \
                = launch_options
        except (KeyError, TypeError):
            self.localconfig["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]["Apps"][prefix]["LaunchOptions"] \
                = launch_options

        self.save_local_config(self.localconfig)

    # noinspection PyTypeChecker
    def del_launch_option(self, prefix: str, key_type: str, key: str):
        original_launch_options = self.get_launch_options(prefix)
        key_types = ["env_vars", "command"]
        _fail_msg = f"Fail to delete a launch option for: {prefix}"

        if 0 in [len(self.localconfig), len(original_launch_options)]:
            logging.warning(_fail_msg)
            return

        if key_type not in key_types:
            logging.warning(_fail_msg + f"\nKey type: {key_type} is not valid")
            return

        if key_type == "env_vars":
            if key in original_launch_options["env_vars"]:
                del original_launch_options["env_vars"][key]
        elif key_type == "command":
            if key in original_launch_options["command"]:
                original_launch_options["command"] = original_launch_options["command"].replace(key, "")

        launch_options = ""

        for e, v in original_launch_options["env_vars"].items():
            launch_options += f"{e}={v} "

        launch_options += f"{original_launch_options['command']} %command% {original_launch_options['args']}"
        try:
            self.localconfig["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]["apps"][prefix]["LaunchOptions"] \
                = launch_options
        except (KeyError, TypeError):
            self.localconfig["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]["Apps"][prefix]["LaunchOptions"] \
                = launch_options

        self.save_local_config(self.localconfig)

    def update_bottle(self, config: dict) -> dict:
        pfx = config.get("CompatData")
        launch_options = self.get_launch_options(pfx)
        _fail_msg = f"Fail to update bottle for: {pfx}"

        args = launch_options.get("args", "")
        if isinstance(args, dict) or args == "{}":
            args = ""

        winecmd = WineCommand(config, "%command%", args)
        command = winecmd.get_cmd("%command%", return_steam_cmd=True)
        env_vars = winecmd.get_env(launch_options["env_vars"], return_steam_env=True)

        if "%command%" in command:
            command, _args = command.split("%command%")
            args = args + " " + _args

        options = {
            "command": command,
            "args": args,
            "env_vars": env_vars
        }
        self.set_launch_options(pfx, options)
        self.config = config
        return config

    @staticmethod
    def launch_app(prefix: str):
        logging.info(f"Launching AppID {prefix} with Steam")
        cmd = [
            "xdg-open",
            "steam://rungameid/{}".format(prefix)
        ]
        subprocess.Popen(cmd)

    def get_runners(self) -> dict:
        """
        TODO: not used, here for reference or later use
              Bottles get Proton runner from config_info file
        """
        if self.steamapps_path is None:
            return {}

        proton_paths = glob(f"{self.steamapps_path}/common/Proton -*")
        runners = {}

        for proton_path in proton_paths:
            _name = os.path.basename(proton_path)
            runners[_name] = {
                "path": proton_path
            }

        return runners

    def add_shortcut(self, program_name: str, program_path: str):
        logging.info(f"Adding shortcut for {program_name}")
        cmd = "xdg-open"
        args = "bottles:run/'{0}'/'{1}'"

        if self.userdata_path is None:
            logging.warning("Userdata path is not set")
            return Result(False)
        
        confs = glob(os.path.join(self.userdata_path, "*/config/"))
        shortcut = {
            "AppName": program_name,
            "Exe": cmd,
            "StartDir": ManagerUtils.get_bottle_path(self.config),
            "icon": ManagerUtils.extract_icon(self.config, program_name, program_path),
            "ShortcutPath": "",
            "LaunchOptions": args.format(self.config["Path"], program_name),
            "IsHidden": 0,
            "AllowDesktopConfig": 1,
            "AllowOverlay": 1,
            "OpenVR": 0,
            "Devkit": 0,
            "DevkitGameID": "",
            "DevkitOverrideAppID": "",
            "LastPlayTime": 0,
            "tags": {"0": "Bottles"}
        }

        for c in confs:
            _shortcuts = {}
            _existing = {}

            if os.path.exists(os.path.join(c, "shortcuts.vdf")):
                with open(os.path.join(c, "shortcuts.vdf"), "rb") as f:
                    try:
                        _existing = vdf.binary_loads(f.read()).get("shortcuts", {})
                    except:
                        continue

            _all = list(_existing.values()) + [shortcut]
            _shortcuts = {"shortcuts": {str(i): s for i, s in enumerate(_all)}}

            with open(os.path.join(c, "shortcuts.vdf"), "wb") as f:
                f.write(vdf.binary_dumps(_shortcuts))

        logging.info(f"Added shortcut for {program_name}")
        return Result(True)
