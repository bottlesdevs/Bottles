# manager.py
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
import hashlib
import subprocess
import random
import time
import uuid
from bottles.backend.utils import yaml
import shutil
import fnmatch
import contextlib
from glob import glob
from datetime import datetime
from gettext import gettext as _
from typing import Union, NewType, Any, List
from gi.repository import GLib

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.runner import Runner
from bottles.backend.models.result import Result
from bottles.backend.models.samples import Samples
from bottles.backend.globals import Paths
from bottles.backend.managers.journal import JournalManager, JournalSeverity
from bottles.backend.managers.template import TemplateManager
from bottles.backend.managers.versioning import VersioningManager
from bottles.backend.managers.repository import RepositoryManager
from bottles.backend.managers.component import ComponentManager
from bottles.backend.managers.installer import InstallerManager
from bottles.backend.managers.dependency import DependencyManager
from bottles.backend.managers.steam import SteamManager
from bottles.backend.managers.epicgamesstore import EpicGamesStoreManager
from bottles.backend.managers.ubisoftconnect import UbisoftConnectManager
from bottles.backend.utils.file import FileUtils
from bottles.backend.utils.lnk import LnkUtils
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.generic import sort_by_version
from bottles.backend.utils.decorators import cache
from bottles.backend.managers.importer import ImportManager
from bottles.backend.layers import Layer, LayersStore
from bottles.backend.dlls.dxvk import DXVKComponent
from bottles.backend.dlls.vkd3d import VKD3DComponent
from bottles.backend.dlls.nvapi import NVAPIComponent
from bottles.backend.dlls.latencyflex import LatencyFleXComponent
from bottles.backend.wine.uninstaller import Uninstaller
from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.wine.wineserver import WineServer
from bottles.backend.wine.reg import Reg
from bottles.backend.wine.regkeys import RegKeys
from bottles.backend.wine.winepath import WinePath

logging = Logger()


class Manager:
    """
    This is the core of Bottles, everything starts from here. There should
    be only one instance of this class, as it checks for the existence of
    the bottles' directories and creates them if they don't exist. Also
    check for components, dependencies, and installers so this check should
    not be performed every time the manager is initialized.

    NOTE: This class is under heavy-refactoring, so close your eyes
          and enjoy °L°
    """

    # component lists
    runtimes_available = []
    winebridge_available = []
    runners_available = []
    dxvk_available = []
    vkd3d_available = []
    nvapi_available = []
    latencyflex_available = []
    local_bottles = {}
    supported_runtimes = {}
    supported_winebridge = {}
    supported_wine_runners = {}
    supported_proton_runners = {}
    supported_dxvk = {}
    supported_vkd3d = {}
    supported_nvapi = {}
    supported_latencyflex = {}
    supported_dependencies = {}
    supported_installers = {}

    def __init__(self, window, is_cli=False, repo_fn_update=None, **kwargs):
        super().__init__(**kwargs)

        times = {"start": time.time()}

        # common variables
        self.window = window
        self.settings = window.settings
        self.utils_conn = window.utils_conn
        self.is_cli = is_cli
        _offline = not window.utils_conn.check_connection()

        self.repository_manager = RepositoryManager(repo_fn_update)
        times["RepositoryManager"] = time.time()

        self.versioning_manager = VersioningManager(window, self)
        times["VersioningManager"] = time.time()

        self.component_manager = ComponentManager(self, _offline)
        times["ComponentManager"] = time.time()

        self.installer_manager = InstallerManager(self, _offline)
        times["InstallerManager"] = time.time()

        self.dependency_manager = DependencyManager(self, _offline)
        times["DependencyManager"] = time.time()

        self.import_manager = ImportManager(self)
        times["ImportManager"] = time.time()

        self.steam_manager = SteamManager()
        times["SteamManager"] = time.time()

        if not is_cli:
            times.update(self.checks(install_latest=False, first_run=True))
        else:
            logging.set_silent()

        if "BOOT_TIME" in os.environ:
            _temp_times = times.copy()
            last = 0
            times_str = "Boot times:"
            for f, t in _temp_times.items():
                if last == 0:
                    last = int(round(t))
                    continue
                t = int(round(t))
                times_str += f"\n\t - {f} took: {t - last}s"
                last = t
            logging.info(times_str)

    def checks(self, install_latest=False, first_run=False):
        logging.info("Performing Bottles checks…")
        times = {}

        self.check_app_dirs()
        times["check_app_dirs"] = time.time()

        self.check_dxvk(install_latest)
        times["check_dxvk"] = time.time()

        self.check_vkd3d(install_latest)
        times["check_vkd3d"] = time.time()

        self.check_nvapi(install_latest)
        times["check_nvapi"] = time.time()

        self.check_latencyflex(install_latest)
        times["check_latencyflex"] = time.time()

        self.check_runtimes(install_latest)
        times["check_runtimes"] = time.time()

        self.check_winebridge(install_latest)
        times["check_winebridge"] = time.time()

        self.check_runners(install_latest)
        times["check_runners"] = time.time()

        if first_run:
            self.organize_components()
            times["organize_components"] = time.time()
            self.__clear_temp()
            times["clear_temp"] = time.time()

        self.organize_dependencies()
        times["organize_dependencies"] = time.time()

        self.organize_installers()
        times["organize_installers"] = time.time()

        self.check_bottles()
        times["check_bottles"] = time.time()

        return times

    def __clear_temp(self, force: bool = False):
        """Clears the temp directory if user setting allows it. Use the force
        parameter to force clearing the directory.
        """
        if self.settings.get_boolean("temp") or force:
            try:
                shutil.rmtree(Paths.temp)
                os.makedirs(Paths.temp, exist_ok=True)
                logging.info("Temp directory cleaned successfully!")
            except FileNotFoundError:
                self.check_app_dirs()

    def update_bottles(self, silent: bool = False):
        """Checks for new bottles and update the list view.
        TODO: list view should not be updated by the backend"""
        self.check_bottles(silent)
        with contextlib.suppress(AttributeError):
            self.window.page_list.update_bottles()

    def check_app_dirs(self):
        """
        Checks for the existence of the bottles' directories, and creates them
        if they don't exist.
        """
        if not os.path.isdir(Paths.runners):
            logging.info("Runners path doesn't exist, creating now.")
            os.makedirs(Paths.runners, exist_ok=True)

        if not os.path.isdir(Paths.runtimes):
            logging.info("Runtimes path doesn't exist, creating now.")
            os.makedirs(Paths.runtimes, exist_ok=True)

        if not os.path.isdir(Paths.winebridge):
            logging.info("WineBridge path doesn't exist, creating now.")
            os.makedirs(Paths.winebridge, exist_ok=True)

        if not os.path.isdir(Paths.bottles):
            logging.info("Bottles path doesn't exist, creating now.")
            os.makedirs(Paths.bottles, exist_ok=True)

        if self.settings.get_boolean("steam-proton-support") and self.steam_manager.is_steam_supported:
            if not os.path.isdir(Paths.steam):
                logging.info("Steam path doesn't exist, creating now.")
                os.makedirs(Paths.steam, exist_ok=True)

        if not os.path.isdir(Paths.layers):
            logging.info("Layers path doesn't exist, creating now.")
            os.makedirs(Paths.layers, exist_ok=True)

        if not os.path.isdir(Paths.dxvk):
            logging.info("Dxvk path doesn't exist, creating now.")
            os.makedirs(Paths.dxvk, exist_ok=True)

        if not os.path.isdir(Paths.vkd3d):
            logging.info("Vkd3d path doesn't exist, creating now.")
            os.makedirs(Paths.vkd3d, exist_ok=True)

        if not os.path.isdir(Paths.nvapi):
            logging.info("Nvapi path doesn't exist, creating now.")
            os.makedirs(Paths.nvapi, exist_ok=True)

        if not os.path.isdir(Paths.templates):
            logging.info("Templates path doesn't exist, creating now.")
            os.makedirs(Paths.templates, exist_ok=True)

        if not os.path.isdir(Paths.temp):
            logging.info("Temp path doesn't exist, creating now.")
            os.makedirs(Paths.temp, exist_ok=True)

        if not os.path.isdir(Paths.latencyflex):
            logging.info("LatencyFlex path doesn't exist, creating now.")
            os.makedirs(Paths.latencyflex, exist_ok=True)

    def organize_components(self):
        """Get components catalog and organizes into supported_ lists."""
        catalog = self.component_manager.fetch_catalog()
        if len(catalog) == 0:
            logging.info("No components found.")
            return

        self.supported_wine_runners = catalog["wine"]
        self.supported_proton_runners = catalog["proton"]
        self.supported_runtimes = catalog["runtimes"]
        self.supported_winebridge = catalog["winebridge"]
        self.supported_dxvk = catalog["dxvk"]
        self.supported_vkd3d = catalog["vkd3d"]
        self.supported_nvapi = catalog["nvapi"]
        self.supported_latencyflex = catalog["latencyflex"]

        # handle winebridge updates
        '''
        TODO: retiring winebridge support for now
        if len(self.winebridge_available) == 0 \
                or self.winebridge_available[0] != next(iter(self.supported_winebridge)):
            self.check_winebridge(install_latest=True, update=True)
        '''

    def organize_dependencies(self):
        """Organizes dependencies into supported_dependencies."""
        catalog = self.dependency_manager.fetch_catalog()
        if len(catalog) == 0:
            logging.info("No dependencies found!")
            return

        self.supported_dependencies = catalog

    def organize_installers(self):
        """Organizes installers into supported_installers."""
        catalog = self.installer_manager.fetch_catalog()
        if len(catalog) == 0:
            logging.info("No installers found!")
            return

        self.supported_installers = catalog

    def remove_dependency(self, config: dict, dependency: list):
        """Uninstall a dependency and remove it from the bottle config."""
        dependency = dependency[0]
        logging.info(f"Removing {dependency} dependency from {config['Name']}")
        uninstallers = config.get("Uninstallers", [])

        # run dependency uninstaller if available
        if dependency in uninstallers:
            uninstaller = uninstallers[dependency]
            Uninstaller(config).from_name(uninstaller)

        # remove dependency from bottle configuration
        if dependency in config["Installed_Dependencies"]:
            config["Installed_Dependencies"].remove(dependency)

        self.update_config(
            config,
            key="Installed_Dependencies",
            value=config["Installed_Dependencies"]
        )
        return Result(
            status=True,
            data={"removed": True}
        )

    def check_runners(self, install_latest: bool = True) -> bool:
        """
        Check for available runners (both system and Bottles) and install
        the latest version if install_latest is True. It also masks the
        winemenubuilder tool.
        """
        runners = glob(f"{Paths.runners}/*/")
        self.runners_available = []

        # lock winemenubuilder.exe
        for runner in runners:
            winemenubuilder_paths = [
                f"{runner}lib64/wine/x86_64-windows/winemenubuilder.exe",
                f"{runner}lib/wine/x86_64-windows/winemenubuilder.exe",
                f"{runner}lib32/wine/i386-windows/winemenubuilder.exe",
                f"{runner}lib/wine/i386-windows/winemenubuilder.exe",
            ]
            for winemenubuilder in winemenubuilder_paths:
                if winemenubuilder.startswith("Proton"):
                    continue
                if os.path.isfile(winemenubuilder):
                    os.rename(winemenubuilder, f"{winemenubuilder}.lock")

        # check system wine
        if shutil.which("wine") is not None:
            '''
            If the Wine command is available, get the runner version
            and add it to the runners_available list.
            '''
            version = subprocess.Popen(
                "wine --version",
                stdout=subprocess.PIPE,
                shell=True
            ).communicate()[0].decode("utf-8")
            version = "sys-" + version.split("\n")[0].split(" ")[0]
            self.runners_available.append(version)

        # check bottles runners
        for runner in runners:
            _runner = os.path.basename(os.path.normpath(runner))
            self.runners_available.append(_runner)

        if len(self.runners_available) > 0:
            logging.info("Runners found:\n - {0}".format("\n - ".join(self.runners_available)))

        tmp_runners = [x for x in self.runners_available if not x.startswith('sys-')]

        if len(tmp_runners) == 0 and install_latest:
            logging.warning("No runners found.")

            if self.utils_conn.check_connection():
                # if connected, install the latest runner from repository
                try:
                    if not self.window.settings.get_boolean("release-candidate"):
                        tmp_runners = []
                        for runner in self.supported_wine_runners.items():
                            if runner[1]["Channel"] not in ["rc", "unstable"]:
                                tmp_runners.append(runner)
                        runner_name = next(iter(tmp_runners))[0]
                    else:
                        tmp_runners = self.supported_wine_runners
                        runner_name = next(iter(tmp_runners))
                    self.component_manager.install("runner", runner_name)
                except StopIteration:
                    return False
            else:
                return False

        self.runners_available = sorted(self.runners_available, reverse=True)
        return True

    def check_runtimes(self, install_latest: bool = True) -> bool:
        self.runtimes_available = []
        if "FLATPAK_ID" in os.environ:
            self.runtimes_available = ["flatpak-managed"]
            return True

        runtimes = os.listdir(Paths.runtimes)

        if len(runtimes) == 0:
            if install_latest and self.utils_conn.check_connection():
                logging.warning("No runtime found.")
                try:
                    version = next(iter(self.supported_runtimes))
                    return self.component_manager.install("runtime", version)
                except StopIteration:
                    return False
            return False

        runtime = runtimes[0]  # runtimes cannot be more than one
        manifest = os.path.join(Paths.runtimes, runtime, "manifest.yml")

        if os.path.exists(manifest):
            with open(manifest, "r") as f:
                data = yaml.load(f)
                version = data.get("version")
                if version:
                    version = f"runtime-{version}"
                    self.runtimes_available = [version]

    def check_winebridge(self, install_latest: bool = True, update: bool = False) -> bool:
        self.winebridge_available = []
        winebridge = os.listdir(Paths.winebridge)

        if len(winebridge) == 0 or update:
            if install_latest and self.utils_conn.check_connection():
                logging.warning("No WineBridge found.")
                try:
                    version = next(iter(self.supported_winebridge))
                    self.component_manager.install("winebridge", version)
                    self.winebridge_available = [version]
                    return True
                except StopIteration:
                    return False
            return False

        version_file = os.path.join(Paths.winebridge, "VERSION")
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                version = f.read().strip()
                if version:
                    self.winebridge_available = [f"winebridge-{version}"]

    def check_dxvk(self, install_latest: bool = True):
        res = self.__check_component("dxvk", install_latest)
        if res:
            self.dxvk_available = res

    def check_vkd3d(self, install_latest: bool = True):
        res = self.__check_component("vkd3d", install_latest)
        if res:
            self.vkd3d_available = res

    def check_nvapi(self, install_latest: bool = True):
        res = self.__check_component("nvapi", install_latest)
        if res:
            self.nvapi_available = res

    def check_latencyflex(self, install_latest: bool = True):
        res = self.__check_component("latencyflex", install_latest)
        if res:
            self.latencyflex_available = res

    def __check_component(self, component_type: str, install_latest: bool = True) -> Union[bool, list]:
        components = {
            "dxvk": {
                "available": self.dxvk_available,
                "supported": self.supported_dxvk,
                "path": Paths.dxvk
            },
            "vkd3d": {
                "available": self.vkd3d_available,
                "supported": self.supported_vkd3d,
                "path": Paths.vkd3d
            },
            "nvapi": {
                "available": self.nvapi_available,
                "supported": self.supported_nvapi,
                "path": Paths.nvapi
            },
            "latencyflex": {
                "available": self.latencyflex_available,
                "supported": self.supported_latencyflex,
                "path": Paths.latencyflex
            },
            "runtime": {
                "available": self.runtimes_available,
                "supported": self.supported_runtimes,
                "path": Paths.runtimes
            }
        }

        if component_type not in components:
            logging.warning(f"Unknown component type found: {component_type}")
            raise ValueError("Component type not supported.")

        component = components[component_type]
        component["available"] = os.listdir(component["path"])

        if len(component["available"]) > 0:
            logging.info("{0}s found:\n - {1}".format(
                component_type.capitalize(),
                "\n - ".join(component["available"])
            ))

        if len(component["available"]) == 0 and install_latest:
            logging.warning(f"No {component_type} found.")

            if self.utils_conn.check_connection():
                # if connected, install the latest component from repository
                try:
                    component_version = next(iter(component["supported"]))
                    self.component_manager.install(component_type, component_version)
                    component["available"] = [component_version]
                except StopIteration:
                    return False
            else:
                return False

        try:
            return sort_by_version(component["available"])
        except ValueError:
            return sorted(component["available"], reverse=True)

    @staticmethod
    def launch_layer_program(config, layer):
        """Mount a layer and launch the program on it."""
        logging.info(f"Preparing {len(layer['mounts'])} layer(s)…")
        layer_conf = LayersStore.get_layer_by_uuid(layer['uuid'])
        if not layer_conf:
            logging.error("Layer not found.")
            return False
        program_layer = Layer().init(layer_conf)
        program_layer.mount_bottle(config)
        mounts = []

        for mount in layer['mounts']:
            _layer = LayersStore.get_layer_by_name(mount)
            if not _layer:
                logging.error(f"Layer {mount} not found.")
                return False
            mounts.append(_layer["UUID"])

        for mount in mounts:
            logging.info("Mounting layers…")
            program_layer.mount(_uuid=mount)

        logging.info("Launching program…")
        runtime_conf = program_layer.runtime_conf
        wineboot = WineBoot(runtime_conf)
        wineboot.update()
        Runner.run_layer_executable(runtime_conf, layer)

        logging.info("Program exited, unmounting layers…")
        program_layer.sweep()
        program_layer.save()

    def get_programs(self, config: dict) -> list:
        """
        Get the list of programs (both from the drive and the user defined
        in the bottle configuration file).
        """
        if config is None:
            return []

        bottle = ManagerUtils.get_bottle_path(config)
        winepath = WinePath(config)
        results = glob(
            f"{bottle}/drive_c/users/*/Desktop/*.lnk",
            recursive=True
        )
        results += glob(
            f"{bottle}/drive_c/users/*/Start Menu/Programs/**/*.lnk",
            recursive=True
        )
        results += glob(
            f"{bottle}/drive_c/ProgramData/Microsoft/Windows/Start Menu/Programs/**/*.lnk",
            recursive=True
        )
        results += glob(
            f"{bottle}/drive_c/users/*/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/**/*.lnk",
            recursive=True
        )
        installed_programs = []
        ignored_patterns = [
            "*installer*",
            "*unins*",
            "*setup*",
            "*debug*",
            "*report*",
            "*crash*",
            "*err*",
            "_*",
            "start",
            "OriginEr",
            "*website*",
            "*web site*",
            "*user_manual*"
        ]
        found = []
        ext_programs = config.get("External_Programs")

        '''
        Process External_Programs
        '''
        for program in ext_programs:
            _program = ext_programs[program]
            found.append(_program["executable"] )
            if winepath.is_windows(_program["path"]):
                program_folder = ManagerUtils.get_exe_parent_dir(config, _program["path"])
            else:
                program_folder = os.path.dirname(_program["path"])
            installed_programs.append({
                "executable": _program["executable"],
                "arguments": _program.get("arguments", ""),
                "name": _program["name"],
                "path": _program["path"],
                "folder": _program.get("folder", program_folder),
                "icon": "com.usebottles.bottles-program",
                "script": _program.get("script"),
                "dxvk": _program.get("dxvk", config["Parameters"]["dxvk"]),
                "vkd3d": _program.get("vkd3d", config["Parameters"]["vkd3d"]),
                "dxvk_nvapi": _program.get("dxvk_nvapi", config["Parameters"]["dxvk_nvapi"]),
                "fsr": _program.get("fsr", config["Parameters"]["fsr"]),
                "pulseaudio_latency": _program.get("pulseaudio_latency", config["Parameters"]["pulseaudio_latency"]),
                "virtual_desktop": _program.get("virtual_desktop", config["Parameters"]["virtual_desktop"]),
                "removed": _program.get("removed"),
                "id": _program.get("id")
            })

        for program in results:
            '''
            for each .lnk file, try to get the executable path and
            append it to the installed_programs list with its icon, 
            skip if the path contains the "Uninstall" word.
            '''
            executable_path = LnkUtils.get_data(program)
            if executable_path is None:
                continue
            executable_name = executable_path.split("\\")[-1]
            program_folder = ManagerUtils.get_exe_parent_dir(config, executable_path)
            stop = False

            for pattern in ignored_patterns:
                try:
                    if fnmatch.fnmatch(executable_name.lower(), pattern):
                        stop = True
                        break
                except:  # safe to ignore
                    pass
            if stop:
                continue

            path_check = os.path.join(
                bottle,
                executable_path.replace("C:\\", "drive_c\\").replace("\\", "/")
            )

            if os.path.exists(path_check):
                if executable_name not in found:
                    installed_programs.append({
                        "executable": executable_name,
                        "arguments": "",
                        "name": executable_name.split(".")[0],
                        "path": executable_path,
                        "folder": program_folder,
                        "icon": "com.usebottles.bottles-program",
                        "id": str(uuid.uuid4()),
                        "script": "",
                        "dxvk": config["Parameters"]["dxvk"],
                        "vkd3d": config["Parameters"]["vkd3d"],
                        "dxvk_nvapi": config["Parameters"]["dxvk_nvapi"],
                        "fsr": config["Parameters"]["fsr"],
                        "pulseaudio_latency": config["Parameters"]["pulseaudio_latency"],
                        "virtual_desktop": config["Parameters"]["virtual_desktop"],
                        "auto_discovered": True
                    })
                    found.append(executable_name)
                    
            win_steam_manager = SteamManager(config, is_windows=True)

            if self.window.settings.get_boolean("steam-programs") \
                    and win_steam_manager.is_steam_supported:
                programs_names = [p.get("name", "") for p in installed_programs]
                for app in win_steam_manager.get_installed_apps_as_programs():
                    if app["name"] not in programs_names:
                        installed_programs.append(app)

            if self.window.settings.get_boolean("epic-games") \
                    and EpicGamesStoreManager.is_epic_supported(config):
                programs_names = [p.get("name", "") for p in installed_programs]
                for app in EpicGamesStoreManager.get_installed_games(config):
                    if app["name"] not in programs_names:
                        installed_programs.append(app)

            if self.window.settings.get_boolean("ubisoft-connect") \
                    and UbisoftConnectManager.is_uconnect_supported(config):
                programs_names = [p.get("name", "") for p in installed_programs]
                for app in UbisoftConnectManager.get_installed_games(config):
                    if app["name"] not in programs_names:
                        installed_programs.append(app)

        return installed_programs

    def check_bottles(self, silent: bool = False):
        """
        Check for local bottles and update the local_bottles list.
        Will also mark the broken ones if the configuration file is missing
        TODO: move to bottle.py (Bottle manager)
        """
        bottles = os.listdir(Paths.bottles)

        def process_bottle(bottle):
            _name = bottle
            _bottle = os.path.join(Paths.bottles, bottle)
            _placeholder = os.path.join(_bottle, "placeholder.yml")
            _config = os.path.join(_bottle, "bottle.yml")

            if os.path.exists(_placeholder):
                with open(_placeholder, "r") as f:
                    try:
                        placeholder_yaml = yaml.load(f)
                        if placeholder_yaml.get("Path"):
                            _config = os.path.join(placeholder_yaml.get("Path"), "bottle.yml")
                        else:
                            raise ValueError("Missing Path in placeholder.yml")
                    except (yaml.YAMLError, ValueError):
                        return

            try:
                if not os.path.exists(_config):
                    raise AttributeError
                with open(_config, "r") as f:
                    conf_file_yaml = yaml.load(f)
            except (FileNotFoundError, AttributeError, yaml.YAMLError):
                return

            if conf_file_yaml is None:
                return

            # Clear Latest_Executables on new session start
            if conf_file_yaml.get("Latest_Executables"):
                conf_file_yaml["Latest_Executables"] = []

            # Migrate old programs to [id] and [name]
            # TODO: remove this migration after 2022.9.28
            _temp = {}
            _changed = False
            for k, v in conf_file_yaml.get("External_Programs").items():
                _uuid = str(uuid.uuid4())
                _k = k
                _v = v
                if isinstance(v, str):
                    continue
                try:
                    uuid.UUID(k)
                except (ValueError, TypeError):
                    _k = _uuid
                    _changed = True
                if "id" not in v:
                    _v["id"] = _uuid
                    _changed = True
                if "name" not in v:
                    _v["name"] = _v["executable"].split(".")[0]
                    _changed = True
                _temp[_k] = _v

            if _changed:
                self.update_config(
                    config=conf_file_yaml,
                    key="External_Programs",
                    value=_temp
                )
            conf_file_yaml["External_Programs"] = _temp

            miss_keys = Samples.config.keys() - conf_file_yaml.keys()
            for key in miss_keys:
                logging.warning(f"Key {key} is missing for bottle {_name}, updating…")
                self.update_config(
                    config=conf_file_yaml,
                    key=key,
                    value=Samples.config[key]
                )

            miss_params_keys = Samples.config["Parameters"].keys() - conf_file_yaml["Parameters"].keys()

            for key in miss_params_keys:
                '''
                For each missing key in the bottle configuration, set
                it to the default value.
                '''
                logging.warning(f"Parameters key {key} is missing for bottle {_name}, updating…")
                self.update_config(
                    config=conf_file_yaml,
                    key=key,
                    value=Samples.config["Parameters"][key],
                    scope="Parameters"
                )
            self.local_bottles[conf_file_yaml['Name']] = conf_file_yaml

            for p in [
                os.path.join(_bottle, "cache", "dxvk_state"),
                os.path.join(_bottle, "cache", "gl_shader"),
                os.path.join(_bottle, "cache", "mesa_shader"),
                os.path.join(_bottle, "cache", "vkd3d_shader"),
            ]:
                if not os.path.exists(p):
                    os.makedirs(p)

            for c in os.listdir(_bottle):
                c = str(c)
                if c.endswith(".dxvk-cache"):
                    shutil.move(os.path.join(_bottle, c), os.path.join(_bottle, "cache", "dxvk_state"))
                elif "vkd3d-proton.cache" in c:
                    shutil.move(os.path.join(_bottle, c), os.path.join(_bottle, "cache", "vkd3d_shader"))
                elif c == "GLCache":
                    shutil.move(os.path.join(_bottle, c), os.path.join(_bottle, "cache", "gl_shader"))

        for b in bottles:
            '''
            For each bottle add the path name to the `local_bottles` variable
            and append the config.
            '''
            process_bottle(b)

        if len(self.local_bottles) > 0 and not silent:
            logging.info("Bottles found:\n - {0}".format("\n - ".join(self.local_bottles)))

        if self.settings.get_boolean("steam-proton-support") \
                and self.steam_manager.is_steam_supported \
                and not self.is_cli:
            self.steam_manager.update_bottles()
            self.local_bottles.update(self.steam_manager.list_prefixes())

    # Update parameters in bottle config
    def update_config(
            self,
            config: dict,
            key: str,
            value: Any,
            scope: str = "",
            remove: bool = False,
            fallback: bool = False
    ) -> Union[Result, dict]:
        """
        Update parameters in bottle config. Use the scope argument to
        update the parameters in the specified scope (e.g. Parameters).
        A new key will be created if another already exists and fallback
        is set to True.
        TODO: move to bottle.py (Bottle manager)
        """
        _name = config.get('Name')
        logging.info(f"Setting Key {key}={value} for bottle {_name}…")

        _config = config
        wineboot = WineBoot(_config)
        wineserver = WineServer(_config)
        bottle_path = ManagerUtils.get_bottle_path(config)

        if key == "sync":
            '''
            Workaround <https://github.com/bottlesdevs/Bottles/issues/916>
            Sync type change requires wineserver restart or wine will fail
            to execute any command.
            '''
            wineboot.kill()
            wineserver.wait()

        if scope != "":
            if remove:
                del config[scope][key]
            elif config[scope].get(key) and fallback:
                config[scope][f"{key}-{uuid.uuid4()}"] = value
            else:
                config[scope][key] = value
        else:
            if remove:
                del config[key]
            elif config.get(key) and fallback:
                config[f"{key}-{uuid.uuid4()}"] = value
            else:
                config[key] = value

        with open(os.path.join(bottle_path, "bottle.yml"), "w") as conf_file:
            yaml.dump(config, conf_file, indent=4)
            conf_file.close()

        config["Update_Date"] = str(datetime.now())

        if config.get("Environment") == "Steam":
            config = self.steam_manager.update_bottle(config)

        return Result(status=True, data={"config": config})

    def create_bottle_from_config(self, config: dict) -> bool:
        """Create a bottle from a config dict."""
        logging.info(f"Creating new {config['Name']} bottle from config…")

        for key in Samples.config.keys():
            '''
            If the key is not in the configuration sample, set it to the
            default value.
            '''
            if key not in config.keys():
                self.update_config(
                    config=config,
                    key=key,
                    value=Samples.config[key]
                )

        if config["Runner"] not in self.runners_available:
            '''
            If the runner is not in the list of available runners, set it
            to latest Soda. If there is no Soda, set it to the
            first one.
            '''
            config["Runner"] = self.get_latest_runner("wine")

        if config["DXVK"] not in self.dxvk_available:
            '''
            If the DXVK is not in the list of available DXVKs, set it to
            highest version.
            '''
            config["DXVK"] = sorted(
                [dxvk for dxvk in self.dxvk_available],
                key=lambda x: x.split("-")[-1]
            )[-1]

        if config["VKD3D"] not in self.vkd3d_available:
            '''
            If the VKD3D is not in the list of available VKD3Ds, set it to
            highest version.
            '''
            config["VKD3D"] = sorted(
                [vkd3d for vkd3d in self.vkd3d_available],
                key=lambda x: x.split("-")[-1]
            )[-1]

        if config["NVAPI"] not in self.dxvk_available:
            '''
            If the NVAPI is not in the list of available NVAPIs, set it to
            highest version.
            '''
            config["NVAPI"] = sorted(
                [nvapi for nvapi in self.nvapi_available],
                key=lambda x: x.split("-")[-1]
            )[-1]

        # create the bottle path
        bottle_path = os.path.join(Paths.bottles, config['Name'])

        if not os.path.exists(bottle_path):
            '''
            If the bottle does not exist, create it, else
            append a random number to the name.
            '''
            os.makedirs(bottle_path)
        else:
            rnd = random.randint(100, 200)
            bottle_path = f"{bottle_path}__{rnd}"
            config["Name"] = f"{config['Name']}__{rnd}"
            config["Path"] = f"{config['Path']}__{rnd}"
            os.makedirs(bottle_path)

        # write the bottle config file
        try:
            with open(os.path.join(bottle_path, "bottle.yml"), "w") as conf_file:
                yaml.dump(config, conf_file, indent=4)
                conf_file.close()
        except (OSError, IOError, yaml.YAMLError, FileNotFoundError, PermissionError) as e:
            logging.error(f"Error writing config file {e}")
            return False

        if config["Parameters"]["dxvk"]:
            '''
            If DXVK is enabled, execute the installation script.
            '''
            self.install_dll_component(config, "dxvk")

        if config["Parameters"]["dxvk_nvapi"]:
            '''
            If NVAPI is enabled, execute the substitution of DLLs.
            '''
            self.install_dll_component(config, "nvapi")

        if config["Parameters"]["vkd3d"]:
            '''
            If the VKD3D parameter is set to True, install it
            in the new bottle.
            '''
            self.install_dll_component(config, "vkd3d")

        for dependency in config["Installed_Dependencies"]:
            '''
            Install each declared dependency in the new bottle.
            '''
            if dependency in self.supported_dependencies.keys():
                dep = [dependency, self.supported_dependencies[dependency]]
                self.dependency_manager.install(config, dep)

        logging.info(f"New bottle from config created: {config['Path']}")
        self.update_bottles(silent=True)
        return True

    def create_bottle(
            self,
            name,
            environment: str,
            path: str = "",
            runner: str = False,
            dxvk: bool = False,
            vkd3d: bool = False,
            nvapi: bool = False,
            latencyflex: bool = False,
            versioning: bool = False,
            sandbox: bool = False,
            fn_logger: callable = None,
            arch: str = "win64",
            custom_environment: str = None
    ):
        """
        Create a new bottle from the given arguments.
        TODO: move to bottle.py (Bottle manager)
        """
        def log_update(message):
            if fn_logger:
                GLib.idle_add(fn_logger, message)

        # check for essential components
        check_attempts = 0

        def components_check():
            nonlocal check_attempts

            if check_attempts > 2:
                logging.error("Fail to install components, tried 3 times.", jn=True)
                log_update(_("Fail to install components, tried 3 times."))
                return False

            if 0 in [
                len(self.runners_available),
                len(self.dxvk_available),
                len(self.vkd3d_available),
                len(self.nvapi_available),
                len(self.latencyflex_available)
            ]:
                logging.error("Missing essential components. Installing…")
                log_update(_("Missing essential components. Installing…"))
                self.check_runners()
                self.check_dxvk()
                self.check_vkd3d()
                self.check_nvapi()
                self.check_latencyflex()
                self.organize_components()

                check_attempts += 1
                return components_check()

            return True

        if not components_check():
            return Result(False)

        # default components versions if not specified
        if not runner:
            # if no runner is specified, use the first one from available
            runner = self.get_latest_runner()
        runner_name = runner

        if not dxvk:
            # if no dxvk is specified, use the first one from available
            dxvk = self.dxvk_available[0]
        dxvk_name = dxvk

        if not vkd3d:
            # if no vkd3d is specified, use the first one from available
            vkd3d = self.vkd3d_available[0]
        vkd3d_name = vkd3d

        if not nvapi:
            # if no nvapi is specified, use the first one from available
            nvapi = self.nvapi_available[0]
        nvapi_name = nvapi

        if not latencyflex:
            # if no latencyflex is specified, use the first one from available
            latencyflex = self.latencyflex_available[0]
        latencyflex_name = latencyflex

        # define bottle parameters
        bottle_name = name
        bottle_name_path = bottle_name.replace(" ", "-")

        # get bottle path
        if path == "":
            # if no path is specified, use the name as path
            bottle_custom_path = False
            bottle_complete_path = os.path.join(Paths.bottles, bottle_name_path)
        else:
            bottle_custom_path = True
            bottle_complete_path = os.path.join(path, bottle_name_path)

        # if another bottle with same path exists, append a random number
        if os.path.exists(bottle_complete_path):
            '''
            if bottle path already exists, create a new one
            using the name and a random number.
            '''
            rnd = random.randint(100, 200)
            bottle_name_path = f"{bottle_name_path}__{rnd}"
            bottle_complete_path = f"{bottle_complete_path}__{rnd}"

        # define registers that should be awaited
        reg_files = [
            os.path.join(bottle_complete_path, "system.reg"),
            os.path.join(bottle_complete_path, "user.reg"),
        ]

        # create the bottle directory
        try:
            os.makedirs(bottle_complete_path)
        except:
            logging.error(f"Failed to create bottle directory: {bottle_complete_path}", jn=True)
            log_update(_("Failed to create bottle directory."))
            return Result(False)

        if bottle_custom_path:
            placeholder_dir = os.path.join(Paths.bottles, bottle_name_path)
            try:
                os.makedirs(placeholder_dir)
                with open(os.path.join(placeholder_dir, "placeholder.yml"), "w") as f:
                    placeholder = {"Path": bottle_complete_path}
                    f.write(yaml.dump(placeholder))
            except:
                logging.error(f"Failed to create placeholder directory/file at: {placeholder_dir}", jn=True)
                log_update(_("Failed to create placeholder directory/file."))
                return Result(False)

        # generate bottle configuration
        logging.info("Generating bottle configuration…")
        log_update(_("Generating bottle configuration…"))
        config = Samples.config
        config["Name"] = bottle_name
        config["Arch"] = arch
        config["Runner"] = runner_name
        config["DXVK"] = dxvk_name
        config["VKD3D"] = vkd3d_name
        config["NVAPI"] = nvapi_name
        config["LatencyFleX"] = latencyflex_name
        config["Path"] = bottle_name_path
        if path != "":
            config["Path"] = bottle_complete_path
        config["Custom_Path"] = bottle_custom_path
        config["Environment"] = environment.capitalize()
        config["Creation_Date"] = str(datetime.now())
        config["Update_Date"] = str(datetime.now())
        if versioning:
            config["Versioning"] = True

        # get template
        template = TemplateManager.get_env_template(environment)
        template_updated = False
        if template:
            log_update(_("Template found, applying…"))
            TemplateManager.unpack_template(template, config)
            config["Installed_Dependencies"] = template["config"]["Installed_Dependencies"]
            config["Uninstallers"] = template["config"]["Uninstallers"]

        # initialize wineprefix
        reg = Reg(config)
        rk = RegKeys(config)
        wineboot = WineBoot(config)
        wineserver = WineServer(config)

        # execute wineboot on the bottle path
        log_update(_("The Wine config is being updated…"))
        wineboot.init()
        log_update(_("Wine config updated!"))

        if "FLATPAK_ID" in os.environ or sandbox:
            '''
            If running as Flatpak, or sandbox flag is set to True, unlink home 
            directories and make them as folders.
            '''
            if "FLATPAK_ID":
                log_update(_("Running as Flatpak, sandboxing userdir…"))
            if sandbox:
                log_update(_("Sandboxing userdir…"))
                
            userdir = f"{bottle_complete_path}/drive_c/users"
            if os.path.exists(userdir):
                # userdir may not exists when unpacking a template, safely
                # ignore as it will be created on first winebot.
                links = []
                for user in os.listdir(userdir):
                    _user_dir = os.path.join(userdir, user)

                    if os.path.isdir(_user_dir):
                        for _dir in os.listdir(_user_dir):
                            _dir_path = os.path.join(_user_dir, _dir)
                            if os.path.islink(_dir_path):
                                links.append(_dir_path)
                        
                        _documents_dir = os.path.join(_user_dir, "Documents")
                        if os.path.isdir(_documents_dir):
                            for _dir in os.listdir(_documents_dir):
                                _dir_path = os.path.join(_documents_dir, _dir)
                                if os.path.islink(_dir_path):
                                    links.append(_dir_path)

                        _win_dir = os.path.join(_user_dir, "AppData", "Roaming", "Microsoft", "Windows")
                        if os.path.isdir(_win_dir):
                            for _dir in os.listdir(_win_dir):
                                _dir_path = os.path.join(_win_dir, _dir)
                                if os.path.islink(_dir_path):
                                    links.append(_dir_path)
                
                for link in links:
                    with contextlib.suppress(IOError, OSError):
                        os.unlink(link)
                        os.makedirs(link)

        # wait for registry files to be created
        FileUtils.wait_for_files(reg_files)

        # apply Windows version
        if not template and not custom_environment:
            logging.info("Setting Windows version…")
            log_update(_("Setting Windows version…"))
            if "soda" not in runner_name.lower() \
                    and "caffe" not in runner_name.lower():  # Caffe/Soda came with win10 by default
                rk.set_windows(config["Windows"])
                wineboot.update()

            FileUtils.wait_for_files(reg_files)

            # apply CMD settings
            logging.info("Setting CMD default settings…")
            log_update(_("Apply CMD default settings…"))
            rk.apply_cmd_settings()
            wineboot.update()

            FileUtils.wait_for_files(reg_files)

            # blacklisting processes
            logging.info("Optimizing environment…")
            log_update(_("Optimizing environment…"))
            _blacklist_dll = ["winemenubuilder.exe", "mshtml"]  # avoid gecko, mono popups
            for _dll in _blacklist_dll:
                reg.add(
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=_dll,
                    data=""
                )

        # apply environment configuration
        logging.info(f"Applying environment: [{environment}]…")
        log_update(_("Applying environment: {0}…").format(environment))
        env = None

        if environment.lower() not in ["custom", "layered"]:
            env = Samples.environments[environment.lower()]
        elif custom_environment:
            try:
                with open(custom_environment, "r") as f:
                    env = yaml.load(f.read())
                    logging.warning("Using a custom environment recipe…")
                    log_update(_("(!) Using a custom environment recipe…"))
            except (FileNotFoundError, PermissionError, yaml.YAMLError):
                logging.error("Recipe not not found or not valid…")
                log_update(_("(!) Recipe not not found or not valid…"))
                return Result(False)

            wineboot.kill()

        if env:
            while wineserver.is_alive():
                time.sleep(1)

            for prm in config["Parameters"]:
                if prm in env.get("Parameters", {}):
                    config["Parameters"][prm] = env["Parameters"][prm]

            if (not template and config["Parameters"]["dxvk"]) \
                    or (template and template["config"]["DXVK"] != dxvk):
                # perform dxvk installation if configured
                logging.info("Installing DXVK…")
                log_update(_("Installing DXVK…"))
                self.install_dll_component(config, "dxvk", version=dxvk_name)
                template_updated = True

            if not template and config["Parameters"]["vkd3d"] \
                    or (template and template["config"]["VKD3D"] != vkd3d):
                # perform vkd3d installation if configured
                logging.info("Installing VKD3D…")
                log_update(_("Installing VKD3D…"))
                self.install_dll_component(config, "vkd3d", version=vkd3d_name)
                template_updated = True

            if not template and config["Parameters"]["dxvk_nvapi"] \
                    or (template and template["config"]["NVAPI"] != nvapi):
                # perform nvapi installation if configured
                logging.info("Installing DXVK-NVAPI…")
                log_update(_("Installing DXVK-NVAPI…"))
                self.install_dll_component(config, "dxvk_nvapi", version=nvapi_name)
                template_updated = True

            for dep in env.get("Installed_Dependencies", []):
                if template and dep in template["config"]["Installed_Dependencies"]:
                    continue
                if dep in self.supported_dependencies:
                    _dep = self.supported_dependencies[dep]
                    log_update(_("Installing dependency: %s …") % _dep.get("Description", "n/a"))
                    self.dependency_manager.install(config, [dep, _dep])
                    template_updated = True

        # create Layers key if Layered
        if environment == "Layered":
            config["Layers"] = {}

        # save bottle config
        with open(f"{bottle_complete_path}/bottle.yml", "w") as conf_file:
            yaml.dump(config, conf_file, indent=4)
            conf_file.close()

        if versioning:
            # create first state if versioning enabled
            logging.info("Creating versioning state 0…")
            log_update(_("Creating versioning state 0…"))
            self.versioning_manager.create_state(
                config=config,
                comment="First boot"
            )

        # set status created and UI usability
        logging.info(f"New bottle created: {bottle_name}", jn=True)
        log_update(_("Finalizing…"))

        # wait for all registry changes to be applied
        FileUtils.wait_for_files(reg_files)

        # perform wineboot
        wineboot.update()

        # caching template
        if (not template and environment != "layered") or template_updated:
            logging.info("Caching template…")
            log_update(_("Caching template…"))
            TemplateManager.new(environment, config)

        return Result(
            status=True,
            data={"config": config}
        )

    def __sort_runners(self, prefix: str, fallback: bool = True) -> sorted:
        """
        Return a sorted list of runners for a given prefix. Fallback to the
        first available if fallback argument is True.
        """
        runners = sorted(
            [
                runner
                for runner in self.runners_available
                if runner.startswith(prefix)
            ],
            key=lambda x: x.split("-")[1],
            reverse=True
        )

        if len(runners) > 0:
            return runners[0]

        return self.runners_available[0] if fallback else []

    def get_latest_runner(self, runner_type: str = "wine") -> list:
        """Return the latest available runner for a given type."""
        try:
            if runner_type in ["", "wine"]:
                return self.__sort_runners("soda")
            return self.__sort_runners("proton")
        except IndexError:
            return []

    def delete_bottle(self, config: dict) -> bool:
        """
        Perform wineserver shutdown and delete the bottle.
        TODO: move to bottle.py (Bottle manager)
        """
        logging.info("Stopping bottle…")
        wineboot = WineBoot(config)
        wineserver = WineServer(config)

        wineboot.kill()
        wineserver.wait()

        if config.get("Path"):
            logging.info(f"Removing applications installed with the bottle…")
            for inst in glob(f"{Paths.applications}/{config.get('Name')}--*"):
                os.remove(inst)

            if config.get("Custom_Path"):
                logging.info(f"Removing placeholder…")
                with contextlib.suppress(FileNotFoundError):
                    os.remove(os.path.join(
                        Paths.bottles,
                        os.path.basename(config.get("Path")),
                        "placeholder.yml"
                    ))

            logging.info(f"Removing the bottle…")
            path = ManagerUtils.get_bottle_path(config)
            shutil.rmtree(path, ignore_errors=True)

            if config.get("Path") in self.local_bottles:
                del self.local_bottles[config.get("Path")]

            logging.info(f"Deleted the bottle in: {path}")
            GLib.idle_add(self.window.page_list.update_bottles)

            return True

        logging.error("Empty path found. Disasters unavoidable.")
        return False

    def repair_bottle(self, config: dict) -> bool:
        """
        This function tries to repair a broken bottle, creating a
        new bottle configuration with the latest runner. Each fixed
        bottle will use the Custom environment.
        TODO: move to bottle.py (Bottle manager)
        """
        logging.info(f"Trying to repair the bottle: [{config['Name']}]…")

        wineboot = WineBoot(config)
        bottle_path = f"{Paths.bottles}/{config['Name']}"

        # create new config with path as name and Custom environment
        new_config = Samples.config
        new_config["Name"] = config.get("Name")
        new_config["Runner"] = self.get_latest_runner()
        new_config["Path"] = config.get("Name")
        new_config["Environment"] = "Custom"
        new_config["Creation_Date"] = str(datetime.now())
        new_config["Update_Date"] = str(datetime.now())

        try:
            with open(os.path.join(bottle_path, "bottle.yml"), "w") as conf_file:
                yaml.dump(new_config, conf_file, indent=4)
                conf_file.close()
        except (OSError, IOError, yaml.YAMLError) as e:
            logging.error(f"Failed to repair bottle: {e}")
            return False

        # Execute wineboot in bottle to generate missing files
        wineboot.init()

        # Update bottles
        self.update_bottles()
        return True

    def install_dll_component(
            self,
            config: dict,
            component: str,
            remove: bool = False,
            version: str = False,
            overrides_only: bool = False,
            exclude: list = None
    ) -> Result:
        if exclude is None:
            exclude = []

        if component == "dxvk":
            _version = config.get("DXVK")
            _version = version if version else _version
            if not _version:
                _version = self.dxvk_available[0]
            manager = DXVKComponent(_version)
        elif component == "vkd3d":
            _version = config.get("VKD3D")
            _version = version if version else _version
            if not _version:
                _version = self.vkd3d_available[0]
            manager = VKD3DComponent(_version)
        elif component == "nvapi":
            _version = config.get("NVAPI")
            _version = version if version else _version
            if not _version:
                _version = self.nvapi_available[0]
            manager = NVAPIComponent(_version)
        elif component == "latencyflex":
            _version = config.get("LatencyFleX")
            _version = version if version else _version
            if not _version:
                if len(self.latencyflex_available) == 0:
                    self.check_latencyflex(install_latest=True)
                _version = self.latencyflex_available[0]
            manager = LatencyFleXComponent(_version)
        else:
            return Result(
                status=False,
                data={"message": f"Invalid component: {component}"}
            )

        if remove:
            manager.uninstall(config, exclude)
        else:
            manager.install(config, overrides_only, exclude)

        return Result(status=True)
