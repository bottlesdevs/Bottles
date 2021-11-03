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
from posixpath import join
import subprocess
import random
import yaml
import time
import shutil
import struct
import locale
import urllib.request
import fnmatch
from glob import glob
from datetime import datetime
from gettext import gettext as _
from typing import Union, NewType
from gi.repository import Gtk, GLib

from ..utils import UtilsLogger, RunAsync
from .runner import Runner
from .globals import Samples, BottlesRepositories, Paths, TrdyPaths
from .versioning import RunnerVersioning
from .component import ComponentManager
from .installer import InstallerManager
from .dependency import DependencyManager
from .manager_utils import ManagerUtils

logging = UtilsLogger()

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
    ---
    TODO: a good task for the future can be splitting out all the Bottle
          related code (like, install dxvk, vkd3d, remove ecc) into a
          separate class. So each bottle can be handled separately, reducing
          this class to only checks purposes and to keep the catalogs.
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

        self.check_runners_dir()
        self.check_dxvk(install_latest=False)
        self.check_vkd3d(install_latest=False)
        self.check_nvapi(install_latest=False)
        self.check_runners(install_latest=False)
        self.organize_components()
        self.organize_dependencies()
        self.fetch_installers()
        self.check_bottles()
        self.__clear_temp()

    def __async_checks(self, args=False, no_install=False):
        after, no_install = args
        self.check_runners_dir()
        self.check_dxvk()
        self.check_vkd3d()
        self.check_nvapi()
        self.check_runners(install_latest=not no_install, after=after)
        self.check_bottles()
        self.organize_dependencies()
        self.fetch_installers()

    def checks(self, after=False, no_install=False):
        '''
        This function performs multiple checks and updates, like
        checking for installed components, bottles' paths, populate
        catalogs, etc.
        '''
        RunAsync(self.__async_checks, None, [after, no_install])

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
                self.check_runners_dir()

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

    def check_runners_dir(self):
        '''
        This function checks if the Bottles' default directories 
        exists, if not, they will be created.
        '''
        if not os.path.isdir(Paths.runners):
            logging.info("Runners path doens't exist, creating now.")
            os.makedirs(Paths.runners, exist_ok=True)

        if not os.path.isdir(Paths.bottles):
            logging.info("Bottles path doens't exist, creating now.")
            os.makedirs(Paths.bottles, exist_ok=True)

        if not os.path.isdir(Paths.dxvk):
            logging.info("Dxvk path doens't exist, creating now.")
            os.makedirs(Paths.dxvk, exist_ok=True)

        if not os.path.isdir(Paths.vkd3d):
            logging.info("Vkd3d path doens't exist, creating now.")
            os.makedirs(Paths.vkd3d, exist_ok=True)

        if not os.path.isdir(Paths.nvapi):
            logging.info("Nvapi path doens't exist, creating now.")
            os.makedirs(Paths.nvapi, exist_ok=True)

        if not os.path.isdir(Paths.temp):
            logging.info("Temp path doens't exist, creating now.")
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
        dependency: list,
        widget: Gtk.Widget
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
        uuid = False

        if dependency[0] in config["Uninstallers"]:
            uninst = config["Uninstallers"][dependency[0]]
            command = f"uninstaller --list | grep '{uninst}' | cut -f1 -d\|"
            uuid = Runner.run_command(
                config=config,
                command=command,
                terminal=False,
                environment=False,
                comunicate=True
            )
            uuid = uuid.strip()

        Runner.run_uninstaller(config, uuid)

        # remove dependency from bottle configuration
        config["Installed_Dependencies"].remove(dependency[0])
        self.update_config(
            config,
            key="Installed_Dependencies",
            value=config["Installed_Dependencies"]
        )

        GLib.idle_add(widget.btn_install.set_visible, True)
        GLib.idle_add(widget.btn_remove.set_visible, False)

    def remove_program(self, config: BottleConfig, program_name: str):
        '''
        This function find and executes the uninstaller of a program
        and removes the program from the bottle configuration.
        '''
        logging.info(
            f"Removing program: [{ program_name }] from " +
            f"bottle: [{config['Name']}] config."
        )

        uuid = False
        command = f"uninstaller --list | grep '{program_name}' | cut -f1 -d\|"
        uuid = Runner.run_command(
            config=config,
            command=command,
            terminal=False,
            environment=False,
            comunicate=True
        )
        uuid = uuid.strip()

        Runner.run_uninstaller(config, uuid)

    def check_runners(self, install_latest: bool = True, after=False) -> bool:
        '''
        This function checks for installed Bottles and system runners and
        appends them to the runners_available list. If there are no runners
        available (the sys-wine cannot be the only one), it will install
        the latest vaniglia runner from the repository if connection is
        available, then update the list with the new one. It also locks the 
        winemenubuilder.exe for the Bottles' runners, to prevent them from
        creating invalid desktop and menu entries.
        A very special thanks to Lutris & GloriousEggroll for extra builds <3!
        '''
        runners = glob("%s/*/" % Paths.runners)
        self.runners_available = []

        # lock winemenubuilder.exe
        for runner in runners:
            winemenubuilder_paths = [
                f"{runner}lib64/wine/x86_64-windows/winemenubuilder.exe",
                f"{runner}lib/wine/x86_64-windows/winemenubuilder.exe",
                f"{runner}lib/wine/i386-windows/winemenubuilder.exe",
            ]
            for winemenubuilder in winemenubuilder_paths:
                if winemenubuilder.startswith("Proton"):
                    continue
                if os.path.isfile(winemenubuilder):
                    os.rename(winemenubuilder, winemenubuilder + ".lock")

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
            logging.info(
                f"Runners found: [{'|'.join(self.runners_available)}]"
            )

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
                        component_name=runner_name,
                        after=after
                    )
                except StopIteration:
                    return False
            else:
                return False

        # sort component lists alphabetically
        self.runners_available = sorted(self.runners_available)
        self.dxvk_available = sorted(self.dxvk_available)
        self.nvapi_available = sorted(self.nvapi_available)

        return True

    def check_dxvk(
        self,
        install_latest: bool = True,
        no_async: bool = False
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
            logging.info(f"Dxvk found: [{'|'.join(self.dxvk_available)}]")

        if len(self.dxvk_available) == 0 and install_latest:
            logging.warning("No dxvk found.")

            if self.utils_conn.check_connection():
                # if connected, install latest dxvk from repository
                try:
                    dxvk_version = next(iter(self.supported_dxvk))
                    if no_async:
                        self.component_manager.async_install(
                            ["dxvk", dxvk_version, False, False, False]
                        )
                    else:
                        self.component_manager.install(
                            "dxvk", dxvk_version, checks=False
                        )
                except StopIteration:
                    return False
            else:
                return False
        return True

    def check_vkd3d(
        self,
        install_latest: bool = True,
        no_async: bool = False
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
            logging.info(f"Vkd3d found: [{'|'.join(self.vkd3d_available)}]")

        if len(self.vkd3d_available) == 0 and install_latest:
            logging.warning("No vkd3d found.")

            if self.utils_conn.check_connection():
                # if connected, install latest vkd3d from repository
                try:
                    vkd3d_version = next(iter(self.supported_vkd3d))
                    if no_async:
                        self.component_manager.async_install(
                            ["vkd3d", vkd3d_version, False, False, False]
                        )
                    else:
                        self.component_manager.install(
                            "vkd3d", vkd3d_version, checks=False
                        )
                except StopIteration:
                    return False
            else:
                return False
        return True

    def check_nvapi(
        self,
        install_latest: bool = True,
        no_async: bool = False
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
            logging.info(f"Nvapi found: [{'|'.join(self.nvapi_available)}]")

        if len(self.nvapi_available) == 0 and install_latest:
            logging.warning("No nvapi found.")

            if self.utils_conn.check_connection():
                # if connected, install latest nvapi from repository
                try:
                    nvapi_version = next(iter(self.supported_nvapi))
                    if no_async:
                        self.component_manager.async_install(
                            ["nvapi", nvapi_version, False, False, False]
                        )
                    else:
                        self.component_manager.install(
                            "nvapi", nvapi_version, checks=False
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

        return "application-x-executable"

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

    def get_programs(self, config: BottleConfig) -> list:
        '''
        This function returns the list of installed programs in common
        Windows' paths, with their icons and paths. It also checks for 
        external programs from the bottle configuration.
        '''
        bottle = "%s/%s" % (Paths.bottles, config.get("Path"))
        results = glob(
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

        for program in results:
            '''
            for each .lnk file, try to get the executable path and
            append it to the installed_programs list with its icon, 
            skip if the path contains the "Uninstall" word.
            '''
            path = program.split("/")[-1].replace(".lnk", "")
            executable_path = self.__getLnkData(program)
            executable_name = executable_path.split("\\")[-1][:-4]
            program_folder = self.__get_exe_parent_dir(
                config,
                executable_path
            )
            icon = self.__find_program_icon(executable_name)

            if "Uninstall" in path:
                continue

            path_check = os.path.join(
                bottle,
                executable_path.replace("C:\\", "drive_c\\").replace("\\", "/")
            )

            if os.path.exists(path_check):
                if executable_path not in installed_programs:
                    installed_programs.append(
                        [path, executable_path, icon, program_folder]
                    )

        if config.get("External_Programs"):
            '''
            if the bottle has external programs in the configuration,
            append them to the installed_programs list.
            '''
            ext_programs = config.get("External_Programs")
            for program in ext_programs:
                program_folder = os.path.dirname(ext_programs[program])
                icon = self.__find_program_icon(program)
                installed_programs.append(
                    [program, ext_programs[program], icon, program_folder]
                )

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

        if len(self.local_bottles) > 0 and not silent:
            logging.info(f"Bottles found: {'|'.join(self.local_bottles)}")

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
        logging.info(
            f"Setting Key: [{key}] to [{value}] for "
            f"bottle: [{config['Name']}]…"
        )

        bottle_complete_path = ManagerUtils.get_bottle_path(config)

        if scope != "":
            config[scope][key] = value
            if remove:
                del config[scope][key]
        else:
            config[key] = value
            if remove:
                del config[key]

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
            config["Runner"] = sorted(
                [
                    runner
                    for runner in self.runners_available
                    if runner.startswith("vaniglia")
                ],
                key=lambda x: x.split("-")[-1]
            )[-1]     
        
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
            self.install_dxvk(config)
        
        if config["Parameters"]["dxvk_nvapi"]:
            '''
            If NVAPI is enabled, execute the substitution of DLLs.
            '''
            self.install_nvapi(config)
        
        if config["Parameters"]["vkd3d"]:
            '''
            If the VKD3D parameter is set to True, install it
            in the new bottle.
            '''
            self.install_vkd3d(config)
        
        for dependency in config["Installed_Dependencies"]:
            '''
            Install each declared dependency in the new bottle.
            '''
            if dependency in self.supported_dependencies.keys():
                dep = [
                    dependency,
                    self.supported_dependencies[dependency]
                ]
                self.dependency_manager.async_install([config, dep, None])

        self.update_bottles(silent=True)

        return True

    def async_create_bottle(self, args: list):
        '''
        This function is used to create a new bottle. It is
        called by the create_bottle function.
        '''
        logging.info("Creating the wineprefix…")

        name, environment, path, runner, dxvk, vkd3d, nvapi, versioning, sandbox, dialog, arch = args

        if len(self.runners_available) == 0:
            # if there are no local runners, show preferences
            GLib.idle_add(
                dialog.update_output, 
                _("No runners found, please install one.")
            )
            self.window.show_prefs_view()
            dialog.destroy()
        if len(self.dxvk_available) == 0:
            # if there are no local dxvks, install latest
            GLib.idle_add(
                dialog.update_output, 
                _("No DXVK found, installing the latest version…")
            )
            self.check_dxvk(no_async=True)
        if len(self.vkd3d_available) == 0:
            # if there are no local vkd3ds, install latest
            GLib.idle_add(
                dialog.update_output, 
                _("No VKD3D found, installing the latest version…")
            )
            self.check_vkd3d(no_async=True)
        if len(self.nvapi_available) == 0:
            # if there are no local nvapis, install latest
            GLib.idle_add(
                dialog.update_output, 
                _("No NVAPI found, installing the latest version…")
            )
            self.check_nvapi(no_async=True)

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

        if path == "":
            # if no path is specified, use the name as path
            bottle_custom_path = False
            bottle_complete_path = f"{Paths.bottles}/{bottle_name_path}"
        else:
            bottle_custom_path = True
            bottle_complete_path = path

        if os.path.exists(bottle_complete_path):
            '''
            if bottle path already exists, create a new one
            using the name and a random number.
            '''
            rnd = random.randint(100, 200)
            bottle_complete_path = f"{bottle_complete_path}__{rnd}"

        # create the bottle directory
        os.makedirs(bottle_complete_path)

        # execute wineboot on the bottle path
        GLib.idle_add(
            dialog.update_output, 
            _("The WINE config is being updated…")
        )
        command = [
            "DISPLAY=:3.0",
            "WINEDEBUG=-all",
            f"WINEPREFIX={bottle_complete_path}",
            f"WINEARCH={arch}",
            f"{runner} wineboot /nogui"
        ]
        command = " ".join(command)
        subprocess.Popen(command, shell=True).communicate()
        GLib.idle_add(
            dialog.update_output, 
            _("WINE config updated!")
        )
        time.sleep(.5)

        if "FLATPAK_ID" in os.environ or sandbox:
            '''
            If running as Flatpak, or sandbox flag is set to True, unlink home 
            directories and make them as folders.
            '''
            if "FLATPAK_ID":
                GLib.idle_add(
                    dialog.update_output, 
                    _("Running as Flatpak, creating sandboxed folders…")
                )
            if sandbox:
                GLib.idle_add(
                    dialog.update_output, 
                    _("Creating sandboxed folders…")
                )
            users_dir = glob(f"{bottle_complete_path}/drive_c/users/*/*")

            for user_path in users_dir:
                if os.path.islink(user_path):
                    try:
                        os.unlink(user_path)
                        os.makedirs(user_path)
                    except:
                        pass
            
            GLib.idle_add(
                dialog.update_output, 
                _("Removing old registry…")
            )
            reg_files = [
                "system.reg",
                "user.reg",
                "userdef.reg"
            ]
            for register in reg_files:
                try:
                    shutil.rmtree(f"{bottle_complete_path}/{register}")
                except:
                    pass
            
            GLib.idle_add(
                dialog.update_output,
                _("Re-initializing registry…")
            )
            command = [
                "DISPLAY=:3.0",
                "WINEDEBUG=-all",
                f"WINEPREFIX={bottle_complete_path}",
                f"WINEARCH={arch}",
                f"{runner} wineboot -u /nogui"
            ]
            time.sleep(.5)

        # generate bottle config file
        logging.info("Generating bottle config file…")
        GLib.idle_add(
            dialog.update_output, 
            _("Generating bottle config file…")
        )

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

        # apply environment config
        logging.info(f"Applying environment: [{environment}]…")
        GLib.idle_add(
            dialog.update_output, 
            _("Applying environment: {0}…").format(environment)
        )
        if environment != "Custom":
            environment_parameters = Samples.environments[
                environment.lower()
            ]["Parameters"]
            for parameter in config["Parameters"]:
                if parameter in environment_parameters:
                    config["Parameters"][parameter] = environment_parameters[
                        parameter
                    ]

        time.sleep(.5)

        # save bottle config
        with open(f"{bottle_complete_path}/bottle.yml", "w") as conf_file:
            yaml.dump(config, conf_file, indent=4)
            conf_file.close()

        time.sleep(.5)

        if config["Parameters"]["dxvk"]:
            # perform dxvk installation if configured
            logging.info("Installing DXVK…")
            GLib.idle_add(
                dialog.update_output, 
                _("Installing DXVK…")
            )
            self.async_install_dxvk([config, False, dxvk_name, None])

        if config["Parameters"]["vkd3d"]:
            # perform vkd3d installation if configured
            logging.info("Installing VKD3D…")
            GLib.idle_add(
                dialog.update_output, 
                _("Installing VKD3D…")
            )
            self.async_install_vkd3d([config, False, vkd3d_name, None])

        if config["Parameters"]["dxvk_nvapi"]:
            # perform nvapi installation if configured
            logging.info("Installing DXVK-NVAPI…")
            GLib.idle_add(
                dialog.update_output, 
                _("Installing DXVK-NVAPI…")
            )
            self.async_install_nvapi([config, False, nvapi_name, None])

        time.sleep(.5)

        if versioning:
            # create first state if versioning enabled
            logging.info("Creating versioning state 0…")
            GLib.idle_add(
                dialog.update_output, 
                _("Creating versioning state 0…")
            )
            self.versioning_manager.async_create_state(
                [config, "First boot", False, True, False])

        # set status created and UI usability
        logging.info(f"[{bottle_name}] is now bottled.")
        GLib.idle_add(
            dialog.update_output, 
            _("Your new {0} bottle is now ready.").format(bottle_name)
        )

        time.sleep(.5)

        dialog.finish(config)

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
        dialog: Gtk.Widget = None,
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
        RunAsync(
            self.async_create_bottle,
            None,
            [
                name,
                environment,
                path,
                runner,
                dxvk,
                vkd3d,
                nvapi,
                versioning,
                sandbox,
                dialog,
                arch
            ]
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
                return self.__sort_runners("vaniglia")
            return self.__sort_runners("proton")
        except IndexError:
            return "Undefined"

    def async_delete_bottle(self, args: list) -> bool:
        '''
        This function deletes the given bottle. It is called
        from the delete_bottle function.
        '''
        config = args[0]

        logging.info("Stopping bottle…")
        Runner.send_status(config, "kill")

        logging.info("Deleting bottle…")

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
            self.window.page_list.update_bottles()

            return True

        logging.error("Empty path found. Disasters unavoidable.")
        return False

    def delete_bottle(self, config: BottleConfig):
        '''
        This function deletes the given bottle, consisting of
        the configuration and files.
        '''
        RunAsync(self.async_delete_bottle, None, [config])

    def repair_bottle(self, config: BottleConfig) -> bool:
        '''
        This function tries to repair a broken bottle, creating a
        new bottle configuration with the latest runner. Each fixed
        bottle will use the Custom environment.
        '''
        logging.info(
            f"Trying to repair the bottle: [{config['Name']}]…"
        )

        bottle_complete_path = f"{Paths.bottles}/{config['Name']}"

        # create new config with path as name and Custom environment
        new_config = Samples.config
        new_config["Name"] = config.get("Name")
        new_config["Runner"] = self.runners_available[0]
        new_config["Path"] = config.get("Name")
        new_config["Environment"] = "Custom"
        new_config["Creation_Date"] = str(datetime.now())
        new_config["Update_Date"] = str(datetime.now())

        try:
            with open("%s/bottle.yml" % bottle_complete_path,
                      "w") as conf_file:
                yaml.dump(new_config, conf_file, indent=4)
                conf_file.close()
        except:
            return False

        # Execute wineboot in bottle to generate missing files
        Runner.run_wineboot(new_config)

        # Update bottles
        self.update_bottles()
        return True

    def async_install_dxvk(self, args: list):
        '''
        This function installs the givven DXVK version in a bottle. It can
        also be used to remove the DXVK version if remove is set to True.
        '''
        config, remove, version, widget = args
        logging.info(f"Installing dxvk for bottle: [{config['Name']}].")

        if version:
            dxvk_version = version
        else:
            dxvk_version = config.get("DXVK")

        option = "uninstall" if remove else "install"

        command = [
            'DISPLAY=:3.0',
            f'WINEPREFIX="{Paths.bottles}/{config.get("Path")}"',
            f'PATH="{Paths.runners}/{config.get("Runner")}/bin:$PATH"',
            f'{Paths.dxvk}/{dxvk_version}/setup_dxvk.sh',
            option,
            '--with-d3d10'
        ]
        command = " ".join(command)
        res = subprocess.Popen(command, shell=True).communicate()

        if widget:
            return GLib.idle_add(widget.set_sensitive, True)
        return res

    def install_dxvk(
        self,
        config: BottleConfig,
        remove: bool = False,
        version: str = False,
        widget: Gtk.Widget = None
    ) -> bool:
        RunAsync(
            self.async_install_dxvk,
            None,
            [config, remove, version, widget]
        )

    def async_install_vkd3d(self, args):
        '''
        This function installs the givven VKD3D version in a bottle. It can
        also be used to remove the VKD3D version if remove is set to True.
        '''
        config, remove, version, widget = args
        logging.info(
            f"Installing vkd3d for bottle: [{config['Name']}]."
        )

        vkd3d_version = config.get("VKD3D")
        if version:
            vkd3d_version = version

        if not vkd3d_version:
            vkd3d_version = self.vkd3d_available[0]
            self.update_config(config, "VKD3D", vkd3d_version)

        option = "uninstall" if remove else "install"

        command = [
            'DISPLAY=:3.0',
            f'WINEPREFIX="{Paths.bottles}/{config.get("Path")}"',
            f'PATH="{Paths.runners}/{config.get("Runner")}/bin:$PATH"',
            f'{Paths.vkd3d}/{vkd3d_version}/setup_vkd3d_proton.sh',
            option
        ]
        res = subprocess.Popen(command, shell=True).communicate()

        if widget:
            return GLib.idle_add(widget.set_sensitive, True)
        return res

    def install_vkd3d(
        self,
        config: BottleConfig,
        remove: bool = False,
        version: str = False,
        widget: Gtk.Widget = None
    ) -> bool:
        RunAsync(
            self.async_install_vkd3d,
            None,
            [config, remove, version, widget]
        )

    def async_install_nvapi(self, args: list):
        '''
        This function installs the givven DXVK-NVAPI version in a bottle. It
        can also be used to remove it if remove is set to True.
        '''
        config, remove, version, widget = args

        if version:
            nvapi_version = version
        else:
            nvapi_version = config.get("NVAPI")

        win_path = f"{Paths.bottles}/{config['Path']}/drive_c/windows/"
        nvapi_path = f"{Paths.nvapi}/{nvapi_version}"
        dlls = {
            "x32": ["nvapi.dll"],
            "x64": ["nvapi64.dll"]
        }
        
        for dll in dlls:
            if dll == "x32":
                inst_path = f"{win_path}system32/"
            else:
                inst_path = f"{win_path}syswow64/"
            
            for dll_file in dlls[dll]:
                _dll = f"{inst_path}{dll_file}"
                _dll_bck = f"{_dll}.bck"
                if remove:
                    if os.path.exists(_dll_bck):
                        os.rename(_dll_bck, _dll)
                    if os.path.exists(_dll):
                        os.remove(_dll)
                else:
                    if os.path.exists(_dll):
                        os.rename(_dll, _dll_bck)
                    shutil.copy(f"{nvapi_path}/{dll}/{dll_file}", inst_path)

        if widget:
            return GLib.idle_add(widget.set_sensitive, True)
        return True

    def install_nvapi(
        self,
        config: BottleConfig,
        remove: bool = False,
        version: str = False,
        widget: Gtk.Widget = None
    ) -> bool:
        RunAsync(
            self.async_install_nvapi,
            None,
            [config, remove, version, widget]
        )

    def remove_dxvk(self, config: BottleConfig, widget: Gtk.Widget = None):
        '''
        This is a wrapper function for the install_dxvk function,
        using the remove option.
        '''
        logging.info(f"Removing dxvk for bottle: [{config['Name']}].")

        self.install_dxvk(config, remove=True, widget=widget)

    def remove_vkd3d(self, config: BottleConfig, widget: Gtk.Widget = None):
        '''
        This is a wrapper function for the install_vkd3d function,
        using the remove option.
        '''
        logging.info(f"Removing VKD3D for bottle: [{config['Name']}].")

        self.install_vkd3d(config, remove=True, widget=widget)

    def remove_nvapi(self, config: BottleConfig, widget: Gtk.Widget = None):
        '''
        This is a wrapper function for the install_nvapi function,
        using the remove option.
        '''
        logging.info(f"Removing dxvk-nvapi for bottle: [{config['Name']}].")

        self.install_nvapi(config, remove=True, widget=widget)

    @staticmethod
    def search_wineprefixes() -> list:
        importer_wineprefixes = []

        # search wine prefixes in external managers paths
        lutris_results = glob(f"{TrdyPaths.lutris}/*/")
        playonlinux_results = glob(f"{TrdyPaths.playonlinux}/*/")
        bottlesv1_results = glob(f"{TrdyPaths.bottlesv1}/*/")

        results = lutris_results + playonlinux_results + bottlesv1_results

        # count results
        is_lutris = len(lutris_results)
        is_playonlinux = is_lutris + len(playonlinux_results)
        i = 1

        for wineprefix in results:
            wineprefix_name = wineprefix.split("/")[-2]

            # identify manager by index
            if i <= is_lutris:
                wineprefix_manager = "Lutris"
            elif i <= is_playonlinux:
                wineprefix_manager = "PlayOnLinux"
            else:
                wineprefix_manager = "Bottles v1"

            # check the drive_c path exists
            if os.path.isdir(f"{wineprefix}/drive_c"):
                wineprefix_lock = os.path.isfile(f"{wineprefix}/bottle.lock")
                importer_wineprefixes.append(
                    {
                        "Name": wineprefix_name,
                        "Manager": wineprefix_manager,
                        "Path": wineprefix,
                        "Lock": wineprefix_lock
                    })
            i += 1

        logging.info(f"Found {len(importer_wineprefixes)} wineprefixes ..")
        return importer_wineprefixes

    def import_wineprefix(self, wineprefix: dict, widget: Gtk.Widget) -> bool:
        '''
        This function imports a wineprefix from an external wineprefix
        manager and converts it into a bottle. It also creates a lock file
        in the source path to prevent multiple imports.
        '''
        logging.info(
            f"Importing wineprefix [{wineprefix['Name']}] in a new bottle…"
        )

        # hide btn_import to prevent double imports
        widget.set_visible(False)

        # prepare bottle path for the wine prefix
        bottle_path = "Imported_%s" % wineprefix.get("Name")
        bottle_complete_path = "%s/%s" % (Paths.bottles, bottle_path)

        try:
            os.makedirs(bottle_complete_path, exist_ok=False)
        except:
            logging.error(
                "Error creating bottle path for wineprefix "
                f"[{wineprefix['Name']}], aborting."
            )
            return False

        # create lockfile in source path
        logging.info("Creating lock file in source path…")
        open(f'{wineprefix.get("Path")}/bottle.lock', 'a').close()

        # copy wineprefix files in the new bottle
        command = f"cp -a {wineprefix.get('Path')}/* {bottle_complete_path}/"
        subprocess.Popen(command, shell=True).communicate()

        # create bottle config
        new_config = Samples.config
        new_config["Name"] = wineprefix["Name"]
        new_config["Runner"] = self.get_latest_runner()
        new_config["Path"] = bottle_path
        new_config["Environment"] = "Custom"
        new_config["Creation_Date"] = str(datetime.now())
        new_config["Update_Date"] = str(datetime.now())

        # save config
        with open(f"{bottle_complete_path}/bottle.yml", "w") as conf_file:
            yaml.dump(new_config, conf_file, indent=4)
            conf_file.close()

        # update bottles view
        self.update_bottles(silent=True)

        logging.info(
            f"Wineprefix: [{wineprefix['Name']}] imported!"
        )
        return True

    @staticmethod
    def browse_wineprefix(wineprefix: dict) -> bool:
        '''
        This function popup the system file manager to browse
        the wineprefix path.
        '''
        return ManagerUtils.open_filemanager(
            path_type="custom",
            custom_path=wineprefix.get("Path")
        )
