# manager.py
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
import subprocess
import random
import yaml
import shlex
import shutil
import struct
import locale
import urllib.request
import fnmatch
from glob import glob
from datetime import datetime
from gettext import gettext as _
from typing import NewType
from gi.repository import GLib

from bottles.backend.logger import Logger # pyright: reportMissingImports=false
from bottles.backend.runner import Runner
from bottles.backend.models.result import Result
from bottles.backend.models.samples import Samples
from bottles.backend.globals import BottlesRepositories, Paths
from bottles.backend.managers.versioning import RunnerVersioning
from bottles.backend.managers.component import ComponentManager
from bottles.backend.managers.installer import InstallerManager
from bottles.backend.managers.dependency import DependencyManager
from bottles.backend.utils.file import FileUtils
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.managers.importer import ImportManager
from bottles.backend.layers import Layer, LayersStore
from bottles.backend.dlls.dxvk import DXVKComponent
from bottles.backend.dlls.vkd3d import VKD3DComponent
from bottles.backend.dlls.nvapi import NVAPIComponent
from bottles.backend.wine.uninstaller import Uninstaller
from bottles.backend.wine.wineboot import WineBoot 
from bottles.backend.wine.reg import Reg

logging = Logger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)


class Manager:
    '''
    This is the core of Bottles, everything starts from here. There should
    be only one instance of this class, as it checks for the existence of
    the bottles' directories and creates them if they don't exist. Also
    check for components, dependencies, and installers so this check should
    not be performed every time the manager is initialized.
    
    NOTE: This class is under heavy-refactoring, so close your eyes 
          and enjoy °L°
    '''

    # component lists
    runners_available = []
    dxvk_available = []
    vkd3d_available = []
    nvapi_available = []
    local_bottles = {}
    supported_wine_runners = {}
    supported_proton_runners = {}
    supported_dxvk = {}
    supported_vkd3d = {}
    supported_nvapi = {}
    supported_dependencies = {}
    supported_installers = {}

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # common variables
        self.window = window
        self.settings = window.settings
        self.utils_conn = window.utils_conn
        self.versioning_manager = RunnerVersioning(window, self)
        self.component_manager = ComponentManager(self)
        self.installer_manager = InstallerManager(self)
        self.dependency_manager = DependencyManager(self)
        self.import_manager = ImportManager(self)

        self.checks(install_latest=False, first_run=True)

    def checks(self, install_latest=False, first_run=False):
        logging.info("Performing Bottles checks...")
        self.check_app_dirs()
        self.check_dxvk(install_latest)
        self.check_vkd3d(install_latest)
        self.check_nvapi(install_latest)
        self.check_runners(install_latest)
        if first_run:
            self.organize_components()
            self.__clear_temp()
        self.check_bottles()
        self.organize_dependencies()
        self.fetch_installers()
        # TODO: self.check_vulkan_support()

    def __clear_temp(self, force: bool = False):
        '''
        This function clears the temp folder if the user
        settings allow it, otherwise it can be forced using
        the force argument. If a FileNotFoundError is raised
        it means that the temp folder is empty or non-existing,
        so the bottles' paths check is performed and the
        missing paths will be created.
        '''
        if self.settings.get_boolean("temp") or force:
            try:
                shutil.rmtree(Paths.temp)
                os.makedirs(Paths.temp, exist_ok=True)
                logging.info("Temp path cleaned successfully!")
            except FileNotFoundError:
                logging.error("Failed to clear temp path!")
                self.check_app_dirs()

    def update_bottles(self, silent: bool = False):
        '''
        This function checks for new bottles and updates the
        bottles list view.
        '''
        self.check_bottles(silent)
        try:
            self.window.page_list.update_bottles()
        except AttributeError:
            pass

    def check_app_dirs(self):
        '''
        This function checks if the Bottles' default directories 
        exists, if not, they will be created.
        '''
        if not os.path.isdir(Paths.runners):
            logging.info("Runners path doesn't exist, creating now.")
            os.makedirs(Paths.runners, exist_ok=True)

        if not os.path.isdir(Paths.bottles):
            logging.info("Bottles path doesn't exist, creating now.")
            os.makedirs(Paths.bottles, exist_ok=True)

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

        if not os.path.isdir(Paths.temp):
            logging.info("Temp path doesn't exist, creating now.")
            os.makedirs(Paths.temp, exist_ok=True)

    def organize_components(self):
        '''
        This function gets the components catalog and organizes
        them into the supported_* lists.
        '''
        catalog = self.component_manager.fetch_catalog()
        if len(catalog) == 0:
            logging.info("No components found!")
            return

        self.supported_wine_runners = catalog["wine"]
        self.supported_proton_runners = catalog["proton"]
        self.supported_dxvk = catalog["dxvk"]
        self.supported_vkd3d = catalog["vkd3d"]
        self.supported_nvapi = catalog["nvapi"]

    def organize_dependencies(self):
        '''
        This function gets the dependencies catalog and organizes
        them into the supported_dependencies list.
        '''
        catalog = self.dependency_manager.fetch_catalog()
        if len(catalog) == 0:
            logging.info("No dependencies found!")
            return

        self.supported_dependencies = catalog

    def remove_dependency(
        self,
        config: BottleConfig,
        dependency: list
    ):
        '''
        This function removes a dependency, it will call its 
        uninstaller if it exists and remove the dependency from
        the bottle configuration.
        '''
        logging.info(
            f"Removing dependency: [{dependency[0]}] from " +
            f"bottle: [{config['Name']}] config."
        )

        # run dependency uninstaller if available
        if dependency[0] in config["Uninstallers"]:
            uninst = config["Uninstallers"][dependency[0]]
            Uninstaller(config).from_name(uninst)

        # remove dependency from bottle configuration
        config["Installed_Dependencies"].remove(dependency[0])
        self.update_config(
            config,
            key="Installed_Dependencies",
            value=config["Installed_Dependencies"]
        )
        return Result(
            status=True,
            data={"removed": True}
        )

    def remove_program(self, config: BottleConfig, program_name: str):
        '''
        This function find and executes the uninstaller of a program
        and removes the program from the bottle configuration.
        '''
        logging.info(
            f"Removing program: [{ program_name }] from " +
            f"bottle: [{config['Name']}] config."
        )
        Uninstaller(config).from_name(program_name)

    def check_runners(self, install_latest: bool = True) -> bool:
        '''
        This function checks for installed Bottles and system runners and
        appends them to the runners_available list. If there are no runners
        available (the sys-wine cannot be the only one), it will install
        the latest caffe runner from the repository if connection is
        available, then update the list with the new one. It also locks the 
        winemenubuilder.exe for the Bottles' runners, to prevent them from
        creating invalid desktop and menu entries.
        A very special thanks to Lutris & GloriousEggroll for extra builds <3!
        '''
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
            If the WINE command is available, get the runner version
            and add it to the runners_available list.
            '''
            version = subprocess.Popen(
                "wine --version",
                stdout=subprocess.PIPE,
                shell=True
            ).communicate()[0].decode("utf-8")
            version = f'sys-{version.split(" ")[0]}'
            self.runners_available.append(version)

        # check bottles runners
        for runner in runners:
            self.runners_available.append(runner.split("/")[-2])

        if len(self.runners_available) > 0:
            logging.info("Runners found:\n - {0}".format(
                "\n - ".join(self.runners_available)
            ))

        tmp_runners = [
            x for x in self.runners_available if not x.startswith('sys-')
        ]

        if len(tmp_runners) == 0 and install_latest:
            logging.warning("No runners found.")

            if self.utils_conn.check_connection():
                # if connected, install latest runner from repository
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
                    self.component_manager.install(
                        component_type="runner",
                        component_name=runner_name
                    )
                except StopIteration:
                    return False
            else:
                return False

        # sort component lists alphabetically
        self.runners_available = sorted(self.runners_available, reverse=True)
        self.dxvk_available = sorted(self.dxvk_available, reverse=True)
        self.nvapi_available = sorted(self.nvapi_available, reverse=True)

        return True

    def check_dxvk(
        self,
        install_latest: bool = True
    ) -> bool:
        '''
        This function check for installed DXVKs and appends them to the
        dxvk_available list. If there are none available, it will
        install the latest DXVK from the repository if a connection is
        available, then update the list with the new one.
        '''
        dxvk_list = glob("%s/*/" % Paths.dxvk)
        self.dxvk_available = []

        for dxvk in dxvk_list:
            self.dxvk_available.append(dxvk.split("/")[-2])

        if len(self.dxvk_available) > 0:
            logging.info("DXVKs found:\n - {0}".format(
                "\n - ".join(self.dxvk_available)
            ))
        if len(self.dxvk_available) == 0 and install_latest:
            logging.warning("No dxvk found.")

            if self.utils_conn.check_connection():
                # if connected, install latest dxvk from repository
                try:
                    dxvk_version = next(iter(self.supported_dxvk))
                    self.component_manager.install(
                        component_type="dxvk", 
                        component_name=dxvk_version, 
                        checks=False
                    )
                except StopIteration:
                    return False
            else:
                return False
        return True

    def check_vkd3d(
        self,
        install_latest: bool = True
    ) -> bool:
        '''
        This function check for installed VKD3Ds and appends them to the
        vkd3d_available list. If there are no VKD3Ds available, it will
        install the latest VKD3D from the repository if a connection is
        available, then update the list with the new one.
        '''
        vkd3d_list = glob("%s/*/" % Paths.vkd3d)
        self.vkd3d_available = []

        for vkd3d in vkd3d_list:
            self.vkd3d_available.append(vkd3d.split("/")[-2])

        if len(self.vkd3d_available) > 0:
            logging.info("VKD3Ds found:\n - {0}".format(
                "\n - ".join(self.vkd3d_available)
            ))

        if len(self.vkd3d_available) == 0 and install_latest:
            logging.warning("No vkd3d found.")

            if self.utils_conn.check_connection():
                # if connected, install latest vkd3d from repository
                try:
                    vkd3d_version = next(iter(self.supported_vkd3d))
                    self.component_manager.install(
                        component_type="vkd3d", 
                        component_name=vkd3d_version, 
                        checks=False
                    )
                except StopIteration:
                    return False
            else:
                return False
        return True

    def check_nvapi(
        self,
        install_latest: bool = True
    ) -> bool:
        '''
        This function checks for installed NVAPIs and appends them to the
        nvapi_available list. If there are none available, it will
        install the latest NVAPI from the repository if a connection is
        available, then update the list with the new one.
        '''
        nvapi_list = glob("%s/*/" % Paths.nvapi)
        self.nvapi_available = []

        for nvapi in nvapi_list:
            self.nvapi_available.append(nvapi.split("/")[-2])

        if len(self.nvapi_available) > 0:
            logging.info("NVAPIs found:\n - {0}".format(
                "\n - ".join(self.nvapi_available)
            ))

        if len(self.nvapi_available) == 0 and install_latest:
            logging.warning("No nvapi found.")

            if self.utils_conn.check_connection():
                # if connected, install latest nvapi from repository
                try:
                    nvapi_version = next(iter(self.supported_nvapi))
                    self.component_manager.install(
                        component_type="nvapi", 
                        component_name=nvapi_version, 
                        checks=False
                    )
                except StopIteration:
                    return False
            else:
                return False
        return True

    def __find_program_icon(self, program_name):
        '''
        This function searches for an icon by program name, in the
        user's home icons directory. If the icon is not found, it
        will return the default "application-x-executable".
        '''
        logging.debug(f"Searching [{program_name}] icon..")
        pattern = f"*{program_name}*"

        for root, dirs, files in os.walk(Paths.icons_user):
            for name in files:
                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    name = name.split("/")[-1][:-4]
                    return name

        if "FLATPAK_ID" in os.environ:
            '''
            Flatpak has no access to the user's home directory, so
            no icons can be found. Returning an empty string to
            hide the icon instead of returning the default one for
            all the entries in the Programs list.
            '''
            return ""

        return "com.usebottles.bottles-program"

    def __get_exe_parent_dir(self, config, executable_path):
        '''
        This function gets the parent directory for the given
        executable path.
        '''
        p = ""
        if "\\" in executable_path:
            p = "\\".join(executable_path.split("\\")[:-1])
            p = p.replace("C:\\", "\\drive_c\\").replace("\\", "/")
            return ManagerUtils.get_bottle_path(config) + p

        p = "\\".join(executable_path.split("/")[:-1])
        p = f"/drive_c/{p}"
        return p.replace("\\", "/")

    @staticmethod
    def __getLnkData(path):
        '''
        This function gets the data from a .lnk file, and returns
        them in a dictionary. Thanks to @Winand and @Jared for the code.
        <https://gist.github.com/Winand/997ed38269e899eb561991a0c663fa49>
        '''
        with open(path, 'rb') as stream:
            content = stream.read()
            '''
            Skip first 20 bytes (HeaderSize and LinkCLSID)
            read the LinkFlags structure (4 bytes)
            '''
            lflags = struct.unpack('I', content[0x14:0x18])[0]
            position = 0x18

            if (lflags & 0x01) == 1:
                '''
                If the HasLinkTargetIDList bit is set then skip the stored IDList 
                structure and header
                '''
                position = struct.unpack('H', content[0x4C:0x4E])[0] + 0x4E

            last_pos = position
            position += 0x04

            # get how long the file information is (LinkInfoSize)
            length = struct.unpack('I', content[last_pos:position])[0]

            '''
            Skip 12 bytes (LinkInfoHeaderSize, LinkInfoFlags and 
            VolumeIDOffset)
            '''
            position += 0x0C

            # go to the LocalBasePath position
            lbpos = struct.unpack('I', content[position:position+0x04])[0]
            position = last_pos + lbpos

            # read the string at the given position of the determined length
            size = (length + last_pos) - position - 0x02
            content = content[position:position+size].split(b'\x00', 1)

            decode = locale.getdefaultlocale()[1]
            if len(content) > 1:
                decode = 'utf-16'

            return content[-1].decode(decode)

    def launch_layer_program(self, config, layer):
        '''
        This function mount a layer and launches a program on it.
        '''
        logging.info(f"Preparing {len(layer['mounts'])} layer(s)..")
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
            logging.info("Mounting layers..")
            program_layer.mount(uuid=mount)
            
        logging.info("Launching program..")
        Runner.run_layer_executable(config, layer)

        logging.info("Program exited, unmounting layers..")
        program_layer.sweep()
        program_layer.save()

    def get_programs(self, config: BottleConfig) -> list:
        '''
        This function returns the list of installed programs in common
        Windows' paths, with their icons and paths. It also checks for 
        external programs from the bottle configuration.
        '''
        bottle = ManagerUtils.get_bottle_path(config)
        results = glob(
            f"{bottle}/drive_c/users/*/Start Menu/Programs/**/*.lnk",
            recursive=True
        )
        results = glob(
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
            "*uninstall*",
            "*setup*",
            "*debug*",
            "*report*",
            "*crash*",
            "*err*"
        ]
        found = []
        ext_programs = config.get("External_Programs")

        '''
        Process External_Programs
        '''
        for program in ext_programs:
            found.append(program)
            _program = ext_programs[program]
            program_folder = os.path.dirname(_program["path"])
            icon = self.__find_program_icon(program)
            installed_programs.append({
                "executable": _program["executable"],
                "arguments": _program.get("arguments", ""),
                "name": _program["name"],
                "path": _program["path"],
                "folder": program_folder,
                "icon": icon,
                "script": _program.get("script"),
                "removed": _program.get("removed")
            })

        for program in results:
            '''
            for each .lnk file, try to get the executable path and
            append it to the installed_programs list with its icon, 
            skip if the path contains the "Uninstall" word.
            '''
            executable_path = self.__getLnkData(program)
            executable_name = executable_path.split("\\")[-1]
            program_folder = self.__get_exe_parent_dir(
                config,
                executable_path
            )
            icon = self.__find_program_icon(executable_name)

            for pattern in ignored_patterns:
                stop = False
                if fnmatch.fnmatch(executable_name.lower(), pattern):
                    stop = True
                    break
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
                        "icon": icon
                    })
                    found.append(executable_name)

        return installed_programs

    def fetch_installers(self) -> bool:
        '''
        This function fetches the installers from the repository and
        appends them to the supported_installers list. It will return
        True if the installers are found, and False otherwise.
        TODO: this function should be moved to the installer manager.
        '''
        if not self.utils_conn.check_connection():
            return False

        try:
            url = urllib.request.urlopen(BottlesRepositories.installers_index)
            index = yaml.safe_load(url.read())

            for installer in index.items():
                self.supported_installers[installer[0]] = installer[1]
        except:
            logging.error(
                "Cannot fetch installers index from repository."
            )
            return False

    def check_bottles(self, silent: bool = False):
        '''
        This function checks for local bottles and appends them to the
        local_bottles list. If silent is True, it will not update the
        bottles list view. It also tries to update old bottle configurations
        and sets them to broken if the configuration is missing.
        '''
        bottles = glob("%s/*/" % Paths.bottles)

        for bottle in bottles:
            '''
            For each bottle add the path name to the `local_bottles` variable
            and append the config.
            '''
            bottle_name_path = bottle.split("/")[-2]

            try:
                conf_file = open(f"{bottle}/bottle.yml")
                conf_file_yaml = yaml.safe_load(conf_file)
                conf_file.close()
                
                # Migrate old environment_variables to new format
                if "Parameters" in conf_file_yaml:
                    _parameters = conf_file_yaml["Parameters"]
                    if "environment_variables" in _parameters:
                        entries = shlex.split(_parameters["environment_variables"])
                        _env = {}

                        if len(entries) > 0:
                            for e in entries:
                                kv = e.split("=")

                                if len(kv) > 2:
                                    kv[1] = "=".join(kv[1:])
                                    kv = kv[:2]

                                if len(kv) == 2:
                                    _env[kv[0]] = kv[1]
                            
                            conf_file_yaml["Environment_Variables"] = _env
                            if len(_env) > 0:
                                del _parameters["environment_variables"]
                
                # Migrate old Software env to the new Application
                if conf_file_yaml["Environment"] == "Software":
                    conf_file_yaml["Environment"] = "Application"

                # Clear Latest_Executables on new session start
                if conf_file_yaml.get("Latest_Executables"):
                    conf_file_yaml["Latest_Executables"] = []

                miss_keys = Samples.config.keys() - conf_file_yaml.keys()
                for key in miss_keys:
                    logging.warning(
                        f"Key: [{key}] not in bottle: "
                        f"[{bottle.split('/')[-2]}] config, updating."
                    )
                    self.update_config(
                        config=conf_file_yaml,
                        key=key,
                        value=Samples.config[key],
                        no_update=True
                    )

                miss_params_keys = Samples.config["Parameters"].keys(
                ) - conf_file_yaml["Parameters"].keys()

                for key in miss_params_keys:
                    '''
                    For each missing key in the bottle configuration, set
                    it to the default value.
                    '''
                    logging.warning(
                        f"Key: [{key}] not in bottle: "
                        f"[{bottle.split('/')[-2]}] config Parameters, "
                        "updating."
                    )
                    self.update_config(
                        config=conf_file_yaml,
                        key=key,
                        value=Samples.config["Parameters"][key],
                        scope="Parameters",
                        no_update=True
                    )
                self.local_bottles[bottle_name_path] = conf_file_yaml

            except FileNotFoundError:
                new_config_yaml = Samples.config.copy()
                new_config_yaml["Broken"] = True
                new_config_yaml["Name"] = bottle_name_path
                new_config_yaml["Environment"] = "Undefined"
                self.local_bottles[bottle_name_path] = new_config_yaml
            except AttributeError:
                pass

        if len(self.local_bottles) > 0 and not silent:
            logging.info("Bottles found:\n - {0}".format(
                "\n - ".join(self.local_bottles)
            ))

    # Update parameters in bottle config
    def update_config(
        self,
        config: BottleConfig,
        key: str,
        value: str,
        scope: str = "",
        no_update: bool = False,
        remove: bool = False
    ) -> dict:
        '''
        This function can be used to update parameters in a bottle
        configuration. It will return the updated bottle configuration.
        It requires the key and the value to update. If the scope is
        specified, it will update the parameter in the specified scope.
        With the remove flag, it will remove the parameter from the
        configuration. Use no_update to avoid updating the local bottle
        list and view. It also updates the Update_Date key.
        '''
        if "IsLayer" in config:
            return

        logging.info(
            f"Setting Key: [{key}] to [{value}] for "
            f"bottle: [{config['Name']}]…"
        )

        wineboot = WineBoot(config)
        bottle_complete_path = ManagerUtils.get_bottle_path(config)

        if scope != "":
            config[scope][key] = value
            if remove:
                del config[scope][key]
        else:
            config[key] = value
            if remove:
                del config[key]

        if key == "sync":
            '''
            Workaround <https://github.com/bottlesdevs/Bottles/issues/916>
            Sync type change requires wineserver restart or wine will fail
            to execute any command.
            '''
            wineboot.kill()

        with open(f"{bottle_complete_path}/bottle.yml", "w") as conf_file:
            yaml.dump(config, conf_file, indent=4)
            conf_file.close()

        if not no_update:
            self.update_bottles(silent=True)

        config["Update_Date"] = str(datetime.now())
        return config

    def create_bottle_from_config(self, config: dict) -> bool:
        '''
        This function creates a new bottle from a configuration. It will
        return the path of the new bottle.
        '''
        logging.info(
            f"Creating new {config['Name']} bottle from config…"
        )

        for key in Samples.config.keys():
            '''
            If the key is not in the configuration sample, set it to the
            default value.
            '''
            if key not in config.keys():
                self.update_config(
                    config=config,
                    key=key,
                    value=Samples.config[key],
                    no_update=True
                )
        
        if config["Runner"] not in self.runners_available:
            '''
            If the runner is not in the list of available runners, set it
            to latest Vaniglia. If there is no Vaniglia, set it to the
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
        bottle_path = f"{Paths.bottles}/{config['Name']}"

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
            with open(f"{bottle_path}/bottle.yml", "w") as conf_file:
                yaml.dump(config, conf_file, indent=4)
                conf_file.close()
        except:
            logging.error("Could not save the bottle config file.")
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
                dep = [
                    dependency,
                    self.supported_dependencies[dependency]
                ]
                self.dependency_manager.install(config, dep)

        self.update_bottles(silent=True)

        return True

    def create_bottle(
        self,
        name,
        environment: str,
        path: str = False,
        runner: RunnerName = False,
        dxvk: bool = False,
        vkd3d: bool = False,
        nvapi: bool = False,
        versioning: bool = False,
        sandbox: bool = False,
        fn_logger: callable = None,
        arch: str = "win64"
    ):
        '''
        This function creates a new bottle, generate the wineprefix
        with the given runner and arch, install DXVK and VKD3D and
        create a new state if versioning is enabled. It also creates
        the configuration file in the bottle root.
        On Flatpak, it also unlinks all folders from the user directory
        and creates these as normal folders instead.
        '''
        def log_update(message):
            if fn_logger:
                GLib.idle_add(fn_logger, message)
        
        # check for essential components
        check_attempts = 0
        def components_check():
            nonlocal check_attempts

            if check_attempts > 2:
                logging.error("Fail to install components, tried 3 times.")
                log_update(_("Fail to install components, tried 3 times."))
                return False

            if 0 in [
                len(self.runners_available),
                len(self.dxvk_available),
                len(self.vkd3d_available),
                len(self.nvapi_available)
            ]:
                logging.error("Missing essential components. Installing…")
                log_update(_("Missing essential components. Installing…"))
                self.check_runners()
                self.check_dxvk()
                self.check_vkd3d()
                self.check_nvapi()
                self.organize_components()

                check_attempts += 1
                return components_check()

            return True

        if not components_check():
            return False

        # default components versions if not specified
        if not runner:
            # if no runner is specified, use the first one from available
            runner = self.runners_available[0]
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

        if runner.startswith("Proton"):
            # if runner is proton, files are located to the dist path
            if os.path.exists("%s/%s/dist" % (Paths.runners, runner)):
                runner = "%s/dist" % runner
            else:
                runner = "%s/files" % runner

        if runner.startswith("sys-"):
            # if runner is system, get its path
            runner = "wine"
        else:
            runner = "%s/%s/bin/wine" % (Paths.runners, runner)

        # define bottle parameters
        bottle_name = name
        bottle_name_path = bottle_name.replace(" ", "-")

        # get bottle path
        if path == "":
            # if no path is specified, use the name as path
            bottle_custom_path = False
            bottle_complete_path = f"{Paths.bottles}/{bottle_name_path}"
        else:
            bottle_custom_path = True
            bottle_complete_path = path

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
            f"{bottle_complete_path}/system.reg",
            f"{bottle_complete_path}/user.reg"
        ]

        # create the bottle directory
        os.makedirs(bottle_complete_path)
        
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
        config["Path"] = bottle_name_path
        if path != "":
            config["Path"] = bottle_complete_path
        config["Custom_Path"] = bottle_custom_path
        config["Environment"] = environment
        config["Creation_Date"] = str(datetime.now())
        config["Update_Date"] = str(datetime.now())
        if versioning:
            config["Versioning"] = True

        reg = Reg(config)
        wineboot = WineBoot(config)

        # execute wineboot on the bottle path
        log_update(_("The WINE config is being updated…"))
        wineboot.init()
        log_update(_("WINE config updated!"))

        if "FLATPAK_ID" in os.environ or sandbox:
            '''
            If running as Flatpak, or sandbox flag is set to True, unlink home 
            directories and make them as folders.
            '''
            if "FLATPAK_ID":
                log_update(_("Running as Flatpak, sandboxing userdir…"))
            if sandbox:
                log_update(_("Sandboxing userdir…"))
            users_dir = glob(f"{bottle_complete_path}/drive_c/users/*/*")
            users_dir+= glob(f"{bottle_complete_path}/drive_c/users/*/AppData/Roaming/Microsoft/Windows/*")

            for user_path in users_dir:
                if os.path.islink(user_path):
                    try:
                        os.unlink(user_path)
                        os.makedirs(user_path)
                    except:
                        pass
            
        # wait for registry files to be created
        FileUtils.wait_for_files(reg_files)

        # apply Windows version
        logging.info("Setting Windows version…")
        log_update(_("Setting Windows version…"))
        Runner.set_windows(config, config["Windows"])
        wineboot.update()
        
        FileUtils.wait_for_files(reg_files)

        # apply CMD settings
        logging.info("Setting CMD default settings…")
        log_update(_("Apply CMD default settings…"))
        Runner.apply_cmd_settings(config)
        wineboot.update()
        
        FileUtils.wait_for_files(reg_files)
        
        # blacklisting processes
        logging.info("Optimizing environment…")
        log_update(_("Optimizing environment…"))
        _blacklist_dll = ["winemenubuilder.exe"]
        for _dll in _blacklist_dll:
            reg.add(
                key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                value=_dll,
                data=""
            )

        # apply environment configuration
        logging.info(f"Applying environment: [{environment}]…")
        log_update(_("Applying environment: {0}…").format(environment))
        if environment not in ["Custom", "Layered"]:
            env = Samples.environments[environment.lower()]
            wineboot.kill()
            
            for prm in config["Parameters"]:
                if prm in env["Parameters"]:
                    config["Parameters"][prm] = env["Parameters"][prm]

            if config["Parameters"]["dxvk"]:
                # perform dxvk installation if configured
                logging.info("Installing DXVK…")
                log_update(_("Installing DXVK…"))
                self.install_dll_component(config, "dxvk", version=dxvk_name)

            if config["Parameters"]["vkd3d"]:
                # perform vkd3d installation if configured
                logging.info("Installing VKD3D…")
                log_update(_("Installing VKD3D…"))
                self.install_dll_component(config, "vkd3d", version=vkd3d_name)

            if config["Parameters"]["dxvk_nvapi"]:
                # perform nvapi installation if configured
                logging.info("Installing DXVK-NVAPI…")
                log_update(_("Installing DXVK-NVAPI…"))
                self.install_dll_component(config, "dxvk_nvapi", version=nvapi_name)
                    
            for dep in env["Installed_Dependencies"]:
                if dep in self.supported_dependencies:
                    _dep = self.supported_dependencies[dep]
                    log_update(_("Installing dependency: {0}…").format(
                        _dep["Description"]
                    ))
                    self.dependency_manager.install(config, [dep, _dep])
        
        # create Layers key if Layered
        if environment == "Layered":
            config["Layers"] = []

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
        logging.info(f"[{bottle_name}] is now bottled.")
        log_update(_("Finalizing…"))

        # wait for all registry changes to be applied
        FileUtils.wait_for_files(reg_files)
        
        # perform wineboot
        wineboot.update()
        
        return Result(
            status=True,
            data={"config": config}
        )

    def __sort_runners(self, prefix: str, fallback: bool = True) -> sorted:
        '''
        This function returns a list of runners filtering by the givven
        prefix, also sorts the list by name (so the first one is the
        major one). If fallback is True, it will return the first in the list
        if there is no runner for the prefix.
        ''' 
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
        
    def get_latest_runner(self, runner_type: RunnerType = "wine") -> list:
        '''
        This function returns the latest version of the given runner, 
        from the runners_available list.
        '''
        try:
            if runner_type in ["", "wine"]:
                return self.__sort_runners("caffe")
            return self.__sort_runners("proton")
        except IndexError:
            return "Undefined"

    def delete_bottle(self, config: BottleConfig) -> bool:
        '''
        This function deletes the given bottle, consisting of
        the configuration and files.
        '''
        logging.info("Stopping bottle…")
        wineboot = WineBoot(config)
        wineboot.force()

        if config.get("Path"):
            logging.info(f"Removing applications installed with the bottle ..")
            for inst in glob(f"{Paths.applications}/{config.get('Name')}--*"):
                os.remove(inst)

            logging.info(f"Removing the bottle…")
            if not config.get("Custom_Path"):
                path = f"{Paths.bottles}/{config.get('Path')}"

            shutil.rmtree(path, ignore_errors=True)
            try:
                del self.local_bottles[config.get("Path")]
            except KeyError:
                # ref: #676
                pass

            logging.info(f"Deleted the bottle in the [{path}] path")
            GLib.idle_add(self.window.page_list.update_bottles)

            return True

        logging.error("Empty path found. Disasters unavoidable.")
        return False

    def repair_bottle(self, config: BottleConfig) -> bool:
        '''
        This function tries to repair a broken bottle, creating a
        new bottle configuration with the latest runner. Each fixed
        bottle will use the Custom environment.
        '''
        logging.info(
            f"Trying to repair the bottle: [{config['Name']}]…"
        )

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
            with open(f"{bottle_path}/bottle.yml", "w") as conf_file:
                yaml.dump(new_config, conf_file, indent=4)
                conf_file.close()
        except:
            return False

        # Execute wineboot in bottle to generate missing files
        wineboot.init()

        # Update bottles
        self.update_bottles()
        return True

    def install_dll_component(
        self,
        config: BottleConfig,
        component: str,
        remove: bool = False,
        version: str = False,
        overrides_only:bool=False,
        exclude: list = []
    ) -> bool:
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
        