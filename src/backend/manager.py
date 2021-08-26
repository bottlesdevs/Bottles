# runner.py
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
import yaml
import time
import shutil
import re
import urllib.request
import fnmatch

from typing import Union, NewType

from gi.repository import Gtk, GLib

from glob import glob
from pathlib import Path
from datetime import datetime

from ..download import DownloadManager
from ..utils import UtilsLogger, RunAsync, CabExtract, validate_url
from .runner import Runner
from .globals import Samples, BottlesRepositories, Paths, TrdyPaths
from .versioning import RunnerVersioning
from .component import ComponentManager
from .installer import InstallerManager
from .dependency import DependencyManager

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)

class Manager:

    # Component lists
    runners_available = []
    dxvk_available = []
    vkd3d_available = []
    local_bottles = {}
    supported_wine_runners = {}
    supported_proton_runners = {}
    supported_dxvk = {}
    supported_vkd3d = {}
    supported_dependencies = {}
    supported_installers = {}

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # Common variables
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
        self.check_runners(install_latest=False)
        self.organize_components()
        self.organize_dependencies()
        self.fetch_installers()
        self.check_bottles()
        self.clear_temp()

    def async_checks(self, args=False, no_install=False):
        after, no_install = args
        self.check_runners_dir()
        self.check_dxvk()
        self.check_vkd3d()
        self.check_runners(install_latest=not no_install, after=after)
        self.check_bottles()
        self.organize_dependencies()
        self.fetch_installers()

    def checks(self, after=False, no_install=False):
        RunAsync(self.async_checks, None, [after, no_install])

    # Clear temp path
    def clear_temp(self, force: bool = False) -> None:
        if self.settings.get_boolean("temp") or force:
            try:
                shutil.rmtree(Paths.temp)
                os.makedirs(Paths.temp, exist_ok=True)
                logging.info("Temp path cleaned successfully!")
            except FileNotFoundError:
                logging.error("Failed to clear temp path!")
                self.check_runners_dir()

    # Update bottles list var and page_list
    def update_bottles(self, silent: bool = False) -> None:
        self.check_bottles(silent)
        try:
            self.window.page_list.update_bottles()
        except AttributeError:
            return

    # Checks if paths exists, else create
    def check_runners_dir(self) -> None:
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

        if not os.path.isdir(Paths.temp):
            logging.info("Temp path doens't exist, creating now.")
            os.makedirs(Paths.temp, exist_ok=True)
    
    def organize_components(self):
        catalog = self.component_manager.fetch_catalog()
        if len(catalog) == 0:
            logging.info("No components found!")
            return
        
        self.supported_wine_runners = catalog["wine"]
        self.supported_proton_runners = catalog["proton"]
        self.supported_dxvk = catalog["dxvk"]
        self.supported_vkd3d = catalog["vkd3d"]
    
    def organize_dependencies(self):
        catalog = self.dependency_manager.fetch_catalog()
        if len(catalog) == 0:
            logging.info("No dependencies found!")
            return
        
        self.supported_dependencies = catalog

    def remove_dependency(self, config: BottleConfig, dependency: list, widget: Gtk.Widget) -> None:
        logging.info(
            f"Removing dependency: [{ dependency[0]}] from bottle: [{config['Name']}] config.")

        uuid = False

        # Run uninstaller
        if dependency[0] in config["Uninstallers"]:
            uninstaller = config["Uninstallers"][dependency[0]]
            command = f"uninstaller --list | grep '{uninstaller}' | cut -f1 -d\|"
            uuid = Runner().run_command(
                config=config,
                command=command,
                terminal=False,
                environment=False,
                comunicate=True)
            uuid = uuid.strip()

        Runner().run_uninstaller(config, uuid)

        # Remove dependency from bottle config
        config["Installed_Dependencies"].remove(dependency[0])
        self.update_config(config,
                                  "Installed_Dependencies",
                                  config["Installed_Dependencies"])

        # Show installation button and hide remove button
        GLib.idle_add(widget.btn_install.set_visible, True)
        GLib.idle_add(widget.btn_remove.set_visible, False)

    def remove_program(self, config: BottleConfig, program_name: str):
        logging.info(
            f"Removing program: [{ program_name }] from bottle: [{config['Name']}] config.")

        uuid = False

        # Run uninstaller
        command = f"uninstaller --list | grep '{program_name}' | cut -f1 -d\|"
        uuid = Runner().run_command(
            config=config,
            command=command,
            terminal=False,
            environment=False,
            comunicate=True)
        uuid = uuid.strip()

        Runner().run_uninstaller(config, uuid)

    # Run installer

    # Check local runners
    def check_runners(self, install_latest: bool = True, after=False) -> bool:
        runners = glob("%s/*/" % Paths.runners)
        self.runners_available = []

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

        # Check system wine
        if shutil.which("wine") is not None:
            version = subprocess.Popen(
                "wine --version",
                stdout=subprocess.PIPE,
                shell=True).communicate()[0].decode("utf-8")
            version = f'sys-{version.split(" ")[0]}'
            self.runners_available.append(version)

        # Check Bottles runners

        for runner in runners:
            self.runners_available.append(runner.split("/")[-2])

        if len(self.runners_available) > 0:
            logging.info(
                f"Runners found: [{'|'.join(self.runners_available)}]")

        '''
        If there are no locally installed runners, download the latest
        build for vaniglia from the components repository.
        A very special thanks to Lutris & GloriousEggroll for extra builds <3!
        '''

        tmp_runners = [
            x for x in self.runners_available if not x.startswith('sys-')]

        if len(tmp_runners) == 0 and install_latest:
            logging.warning("No runners found.")

            # If connected, install latest runner from repository
            if self.utils_conn.check_connection():
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
                    self.component_manager.install("runner", runner_name, after=after)
                except StopIteration:
                    return False
            else:
                return False

        # Sort component lists alphabetically
        self.runners_available = sorted(self.runners_available)
        self.dxvk_available = sorted(self.dxvk_available)

        return True

    # Check local dxvks
    def check_dxvk(self, install_latest: bool = True, no_async: bool = False) -> bool:
        dxvk_list = glob("%s/*/" % Paths.dxvk)
        self.dxvk_available = []

        for dxvk in dxvk_list:
            self.dxvk_available.append(dxvk.split("/")[-2])

        if len(self.dxvk_available) > 0:
            logging.info(f"Dxvk found: [{'|'.join(self.dxvk_available)}]")

        if len(self.dxvk_available) == 0 and install_latest:
            logging.warning("No dxvk found.")

            # If connected, install latest dxvk from repository
            if self.utils_conn.check_connection():
                try:
                    dxvk_version = next(iter(self.supported_dxvk))
                    if no_async:
                        self.async_component_manager.install(
                            ["dxvk", dxvk_version, False, False, False])
                    else:
                        self.component_manager.install(
                            "dxvk", dxvk_version, checks=False)
                except StopIteration:
                    return False
            else:
                return False
        return True

    # Check local vkd3d
    def check_vkd3d(self, install_latest: bool = True, no_async: bool = False) -> bool:
        vkd3d_list = glob("%s/*/" % Paths.vkd3d)
        self.vkd3d_available = []

        for vkd3d in vkd3d_list:
            self.vkd3d_available.append(vkd3d.split("/")[-2])

        if len(self.vkd3d_available) > 0:
            logging.info(f"Vkd3d found: [{'|'.join(self.vkd3d_available)}]")

        if len(self.vkd3d_available) == 0 and install_latest:
            logging.warning("No vkd3d found.")

            # If connected, install latest vkd3d from repository
            if self.utils_conn.check_connection():
                try:
                    vkd3d_version = next(iter(self.supported_vkd3d))
                    if no_async:
                        self.async_component_manager.install(
                            ["vkd3d", vkd3d_version, False, False, False])
                    else:
                        self.component_manager.install(
                            "vkd3d", vkd3d_version, checks=False)
                except StopIteration:
                    return False
            else:
                return False
        return True

    def __find_program_icon(self, program_name):
        logging.debug(f"Searching [{program_name}] icon..")
        pattern = f"*{program_name}*"

        for root, dirs, files in os.walk(Paths.icons_user):
            for name in files:
                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    name = name.split("/")[-1][:-4]
                    return name

        return "application-x-executable"

    def __get_exe_parent_dir(self, config, executable_path):
        p = ""
        if "\\" in executable_path:
            p = "\\".join(executable_path.split("\\")[:-1])
            p = p.replace("C:\\", "\\drive_c\\").replace("\\", "/")
            return Runner().get_bottle_path(config) + p

        p = "\\".join(executable_path.split("/")[:-1])
        p = f"/drive_c/{p}"
        return p.replace("\\", "/")

    # Get installed programs
    def get_programs(self, config: BottleConfig) -> list:
        '''TODO: Programs found should be stored in a database
        TN: Will be fixed in Trento release'''
        bottle = "%s/%s" % (Paths.bottles, config.get("Path"))
        results = glob("%s/drive_c/users/*/Start Menu/Programs/**/*.lnk" % bottle,
                       recursive=True)
        results += glob("%s/drive_c/ProgramData/Microsoft/Windows/Start Menu/Programs/**/*.lnk" % bottle,
                        recursive=True)
        results += glob("%s/drive_c/users/*/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/**/*.lnk" % bottle,
                        recursive=True)
        installed_programs = []

        # For any .lnk file, check for executable path
        for program in results:
            path = program.split("/")[-1]
            executable_path = ""

            if "Uninstall" in path:
                continue

            try:
                with open(program, "r", encoding='utf-8', errors='ignore') as lnk:
                    lnk = lnk.read()
                    executable_path = re.search('C:(.*).exe', lnk)

                    if executable_path is not None:
                        executable_path = executable_path.group(0)
                    else:
                        executable_path = re.search('C:(.*).bat', lnk).group(0)

                    if executable_path.find("ninstall") > 0:
                        continue

                    path = path.replace(".lnk", "")
                    executable_name = executable_path.split("\\")[-1][:-4]
                    program_folder = self.__get_exe_parent_dir(
                        config, executable_path)

                    icon = self.__find_program_icon(executable_name)
                    installed_programs.append(
                        [path, executable_path, icon, program_folder])
            except:
                pass

        if config.get("External_Programs"):
            ext_programs = config.get("External_Programs")
            for program in ext_programs:
                program_folder = ext_programs[program].split("/")[-1]
                icon = self.__find_program_icon(program)
                installed_programs.append(
                    [program, ext_programs[program], icon, program_folder])

        return installed_programs

    # Fetch installers
    def fetch_installers(self) -> bool:
        if not self.utils_conn.check_connection():
            return False

        try:
            url = urllib.request.urlopen(BottlesRepositories.installers_index)
            index = yaml.safe_load(url.read())

            for installer in index.items():
                self.supported_installers[installer[0]] = installer[1]
        except:
            logging.error(
                "Cannot fetch installers index from repository.")
            return False

    # Check local bottles
    def check_bottles(self, silent: bool = False) -> None:
        bottles = glob("%s/*/" % Paths.bottles)

        '''
        For each bottle add the path name to the `local_bottles` variable
        and append the config
        '''
        for bottle in bottles:
            bottle_name_path = bottle.split("/")[-2]

            try:
                conf_file = open(f"{bottle}/bottle.yml")
                conf_file_yaml = yaml.safe_load(conf_file)
                conf_file.close()
                
                # Update architecture of old bottles
                if conf_file_yaml.get("Arch") in ["", None]:
                    self.update_config(conf_file_yaml,
                                              "Arch",
                                              Samples.config["Arch"])

                miss_keys = Samples.config.keys() - conf_file_yaml.keys()
                for key in miss_keys:
                    logging.warning(
                        f"Key: [{key}] not in bottle: [{bottle.split('/')[-2]}] config, updating.")
                    self.update_config(conf_file_yaml,
                                              key,
                                              Samples.config[key],
                                              no_update=True)

                miss_params_keys = Samples.config["Parameters"].keys(
                ) - conf_file_yaml["Parameters"].keys()
                for key in miss_params_keys:
                    logging.warning(
                        f"Key: [{key}] not in bottle: [{bottle.split('/')[-2]}] config Parameters, updating.")
                    self.update_config(conf_file_yaml,
                                              key,
                                              Samples.config["Parameters"][key],
                                              scope="Parameters",
                                              no_update=True)
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
    def update_config(self, config: BottleConfig, key: str, value: str, scope: str = "", no_update: bool = False, remove: bool = False) -> dict:
        logging.info(
            f"Setting Key: [{key}] to [{value}] for bottle: [{config['Name']}] …")

        bottle_complete_path = Runner().get_bottle_path(config)

        if scope != "":
            config[scope][key] = value
            if remove:
                del config[scope][key]
        else:
            config[key] = value
            if remove:
                del config[key]

        with open("%s/bottle.yml" % bottle_complete_path,
                  "w") as conf_file:
            yaml.dump(config, conf_file, indent=4)
            conf_file.close()

        if not no_update:
            self.update_bottles(silent=True)

        # Update Update_Date in config
        config["Update_Date"] = str(datetime.now())
        return config

    # Create new wineprefix
    def async_create_bottle(self, args: list) -> None:
        logging.info("Creating the wineprefix …")

        name, environment, path, runner, dxvk, vkd3d, versioning, dialog, arch = args

        update_output = dialog.update_output

        # If there are no local runners, dxvks, vkd3ds, install them
        if len(self.runners_available) == 0:
            update_output(_("No runners found, please install one."))
            self.window.show_preferences_view()
            dialog.destroy()
        if len(self.dxvk_available) == 0:
            update_output(_("No dxvk found, installing the latest version …"))
            self.check_dxvk(no_async=True)
        if len(self.vkd3d_available) == 0:
            update_output(_("No vkd3d found, installing the latest version …"))
            self.check_vkd3d(no_async=True)

        if not runner:
            runner = self.runners_available[0]
        runner_name = runner

        if not dxvk:
            dxvk = self.dxvk_available[0]
        dxvk_name = dxvk

        if not vkd3d:
            vkd3d = self.vkd3d_available[0]
        vkd3d_name = vkd3d

        # If runner is proton, files are located to the dist path
        if runner.startswith("Proton"):
            if os.path.exists("%s/%s/dist" % (Paths.runners, runner)):
                runner = "%s/dist" % runner
            else:
                runner = "%s/files" % runner

        # If runner is system
        if runner.startswith("sys-"):
            runner = "wine"
        else:
            runner = "%s/%s/bin/wine" % (Paths.runners, runner)

        # Define bottle parameters
        bottle_name = name
        bottle_name_path = bottle_name.replace(" ", "-")

        if path == "":
            bottle_custom_path = False
            bottle_complete_path = "%s/%s" % (
                Paths.bottles, bottle_name_path)
        else:
            bottle_custom_path = True
            bottle_complete_path = path

        # Make progressbar pulsing
        RunAsync(dialog.pulse, None)

        # Execute wineboot
        update_output(_("The wine config is being updated …"))
        command = "DISPLAY=:3.0 WINEDEBUG=fixme-all WINEPREFIX={path} WINEARCH={arch} {runner} wineboot /nogui".format(
            path=bottle_complete_path,
            arch=arch,
            runner=runner
        )
        subprocess.Popen(command, shell=True).communicate()
        update_output(_("Wine config updated!"))
        time.sleep(1)

        # Generate bottle config file
        logging.info("Generating Bottle config file …")
        update_output(_("Generating Bottle config file …"))

        config = Samples.config
        config["Name"] = bottle_name
        config["Arch"] = arch
        config["Runner"] = runner_name
        config["DXVK"] = dxvk_name
        config["VKD3D"] = vkd3d_name
        if path == "":
            config["Path"] = bottle_name_path
        else:
            config["Path"] = bottle_complete_path
        config["Custom_Path"] = bottle_custom_path
        config["Environment"] = environment
        config["Creation_Date"] = str(datetime.now())
        config["Update_Date"] = str(datetime.now())
        if versioning:
            config["Versioning"] = True

        # Apply environment config
        logging.info(f"Applying environment: [{environment}] …")
        update_output(_("Applying environment: {0} …").format(environment))
        if environment != "Custom":
            environment_parameters = Samples.environments[environment.lower(
            )]["Parameters"]
            for parameter in config["Parameters"]:
                if parameter in environment_parameters:
                    config["Parameters"][parameter] = environment_parameters[parameter]

        time.sleep(1)

        # Save bottle config
        with open(f"{bottle_complete_path}/bottle.yml", "w") as conf_file:
            yaml.dump(config, conf_file, indent=4)
            conf_file.close()

        time.sleep(5)

        # Perform dxvk installation if configured
        if config["Parameters"]["dxvk"]:
            logging.info("Installing dxvk …")
            update_output(_("Installing dxvk …"))
            self.install_dxvk(config, version=dxvk_name)

        # Perform vkd3d installation if configured
        if config["Parameters"]["vkd3d"]:
            logging.info("Installing vkd3d …")
            update_output(_("Installing vkd3d …"))
            self.install_vkd3d(config, version=vkd3d_name)

        time.sleep(1)

        # Create first state if versioning enabled
        if versioning:
            logging.info("Creating versioning state 0 …")
            update_output(_("Creating versioning state 0 …"))
            self.versioning_manager.async_create_bottle_state(
                [config, "First boot", False, True, False])

        # Set status created and UI usability
        logging.info(f"Bottle: [{bottle_name}] successfully created!")
        update_output(
            _("Your new bottle: {0} is now ready!").format(bottle_name))

        time.sleep(2)

        dialog.finish(config)

    def create_bottle(self,
                      name,
                      environment: str,
                      path: str = False,
                      runner: RunnerName = False,
                      dxvk: bool = False,
                      vkd3d: bool = False,
                      versioning: bool = False,
                      dialog: Gtk.Widget = None,
                      arch: str = "win64"
                      ) -> None:
        RunAsync(self.async_create_bottle, None, [name,
                                                  environment,
                                                  path,
                                                  runner,
                                                  dxvk,
                                                  vkd3d,
                                                  versioning,
                                                  dialog,
                                                  arch])

    # Get latest installed runner
    def get_latest_runner(self, runner_type: RunnerType = "wine") -> list:
        try:
            if runner_type in ["", "wine"]:
                return [idx for idx in self.runners_available if idx.lower().startswith("lutris")][0]
            return [idx for idx in self.runners_available if idx.lower().startswith("proton")][0]
        except IndexError:
            return "Undefined"

    # Get bottle path size
    def get_bottle_size(self, config: BottleConfig, human: bool = True) -> Union[str, float]:
        path = config.get("Path")

        if not config.get("Custom_Path"):
            path = "%s/%s" % (Paths.bottles, path)

        return self.get_path_size(path, human)

    # Delete a wineprefix
    def async_delete_bottle(self, args: list) -> bool:
        logging.info("Deleting a bottle …")

        config = args[0]

        if config.get("Path"):
            logging.info(f"Removing applications installed with the bottle ..")
            for inst in glob(f"{Paths.applications}/{config.get('Name')}--*"):
                os.remove(inst)

            logging.info(f"Removing the bottle ..")
            if not config.get("Custom_Path"):
                path = "%s/%s" % (Paths.bottles,
                                  config.get("Path"))

            shutil.rmtree(path)
            del self.local_bottles[config.get("Path")]

            logging.info(f"Successfully deleted bottle in path: [{path}]")
            self.window.page_list.update_bottles()

            return True

        logging.error("Empty path found, failing to avoid disasters.")
        return False

    def delete_bottle(self, config: BottleConfig) -> None:
        RunAsync(self.async_delete_bottle, None, [config])

    #  Repair a bottle generating a new config
    def repair_bottle(self, config: BottleConfig) -> bool:
        logging.info(
            f"Trying to repair the bottle: [{config['Name']}] …")

        bottle_complete_path = f"{Paths.bottles}/{config['Name']}"

        # Create new config with path as name and Custom environment
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
        Runner().run_wineboot(new_config)

        # Update bottles
        self.update_bottles()
        return True

    # Get running wine processes
    @staticmethod
    def get_running_processes() -> list:
        processes = []
        command = "ps -eo pid,pmem,pcpu,stime,time,cmd | grep wine | tr -s ' ' '|'"
        pids = subprocess.check_output(['bash', '-c', command]).decode("utf-8")

        for pid in pids.split("\n"):
            # workaround https://github.com/bottlesdevs/Bottles/issues/396
            if pid.startswith("|"):
                pid = pid[1:]

            process_data = pid.split("|")
            if len(process_data) >= 6 and "grep" not in process_data:
                processes.append({
                    "pid": process_data[0],
                    "pmem": process_data[1],
                    "pcpu": process_data[2],
                    "stime": process_data[3],
                    "time": process_data[4],
                    "cmd": process_data[5]
                })

        return processes

    # Add key from register
    def reg_add(self, config: BottleConfig, key: str, value: str, data: str, keyType: str = False) -> None:
        logging.info(
            f"Adding Key: [{key}] with Value: [{value}] and Data: [{data}] in register bottle: {config['Name']}")

        command = "reg add '%s' /v '%s' /d %s /f" % (key, value, data)

        if keyType:
            command = "reg add '%s' /v '%s' /t %s /d %s /f" % (
                key, value, keyType, data)

        Runner().run_command(config, command)

    # Remove key from register
    def reg_delete(self, config: BottleConfig, key: str, value: str) -> None:
        logging.info(
            f"Removing Value: [{key}] for Key: [{value}] in register bottle: {config['Name']}")

        Runner().run_command(config, "reg delete '%s' /v %s /f" % (
            key, value))

    '''
    Install dxvk using official script
    TODO: A good task for the future is to use the built-in methods
    to install the new dlls and register the override for dxvk.
    '''

    def install_dxvk(self, config: BottleConfig, remove: bool = False, version: str = False) -> bool:
        logging.info(f"Installing dxvk for bottle: [{config['Name']}].")

        if version:
            dxvk_version = version
        else:
            dxvk_version = config.get("DXVK")

        option = "uninstall" if remove else "install"

        command = 'DISPLAY=:3.0 WINEPREFIX="{path}" PATH="{runner}:$PATH" {dxvk_setup} {option} --with-d3d10'.format(
            path="%s/%s" % (Paths.bottles, config.get("Path")),
            runner="%s/%s/bin" % (Paths.runners,
                                  config.get("Runner")),
            dxvk_setup="%s/%s/setup_dxvk.sh" % (
                Paths.dxvk, dxvk_version),
            option=option)

        return subprocess.Popen(command, shell=True).communicate()

    '''
    Install vkd3d using official script
    '''

    def install_vkd3d(self, config: BottleConfig, remove: bool = False, version: str = False) -> bool:
        logging.info(
            f"Installing vkd3d for bottle: [{config['Name']}].")

        if version:
            vkd3d_version = version
        else:
            vkd3d_version = config.get("VKD3D")

        if not vkd3d_version:
            vkd3d_version = self.vkd3d_available[0]
            self.update_config(config, "VKD3D", vkd3d_version)

        option = "uninstall" if remove else "install"

        command = 'DISPLAY=:3.0 WINEPREFIX="{path}" PATH="{runner}:$PATH" {vkd3d_setup} {option}'.format(
            path="%s/%s" % (Paths.bottles, config.get("Path")),
            runner="%s/%s/bin" % (Paths.runners,
                                  config.get("Runner")),
            vkd3d_setup="%s/%s/setup_vkd3d_proton.sh" % (
                Paths.vkd3d, vkd3d_version),
            option=option)

        return subprocess.Popen(command, shell=True).communicate()

    # Remove dxvk using official script
    def remove_dxvk(self, config: BottleConfig) -> None:
        logging.info(f"Removing dxvk for bottle: [{config['Name']}].")

        self.install_dxvk(config, remove=True)

    # Remove vkd3d using official script
    def remove_vkd3d(self, config: BottleConfig) -> None:
        logging.info(f"Removing vkd3d for bottle: [{config['Name']}].")

        self.install_vkd3d(config, remove=True)

    # Override dlls in system32/syswow64 paths
    def dll_override(self, config: BottleConfig, arch: str, dlls: list, source: str, revert: bool = False) -> bool:
        arch = "system32" if arch == 32 else "syswow64"
        path = "%s/%s/drive_c/windows/%s" % (Paths.bottles,
                                             config.get("Path"),
                                             arch)
        # Restore dll from backup
        try:
            if revert:
                for dll in dlls:
                    shutil.move("%s/%s.back" %
                                (path, dll), "%s/%s" % (path, dll))
            else:
                '''
                Backup old dlls and install new one
                '''
                for dll in dlls:
                    shutil.move("%s/%s" % (path, dll),
                                "%s/%s.old" % (path, dll))
                    shutil.copy("%s/%s" % (source, dll), "%s/%s" % (path, dll))
        except:
            return False
        return True

    # Toggle virtual desktop for a bottle
    def toggle_virtual_desktop(self, config: BottleConfig, state: bool, resolution: str = "800x600") -> None:
        key = "HKEY_CURRENT_USER\\Software\\Wine\\Explorer\\Desktops"
        if state:
            self.reg_add(config, key, "Default", resolution)
        else:
            self.reg_delete(config, key, "Default")

    @staticmethod
    def search_wineprefixes() -> list:
        importer_wineprefixes = []

        # Search wine prefixes in external managers paths
        lutris_results = glob(f"{TrdyPaths.lutris}/*/")
        playonlinux_results = glob(f"{TrdyPaths.playonlinux}/*/")
        bottlesv1_results = glob(f"{TrdyPaths.bottlesv1}/*/")

        results = lutris_results + playonlinux_results + bottlesv1_results

        # Count results
        is_lutris = len(lutris_results)
        is_playonlinux = is_lutris + len(playonlinux_results)
        i = 1

        for wineprefix in results:
            wineprefix_name = wineprefix.split("/")[-2]

            # Identify manager by index
            if i <= is_lutris:
                wineprefix_manager = "Lutris"
            elif i <= is_playonlinux:
                wineprefix_manager = "PlayOnLinux"
            else:
                wineprefix_manager = "Bottles v1"

            # Check the drive_c path exists
            if os.path.isdir("%s/drive_c" % wineprefix):
                wineprefix_lock = os.path.isfile("%s/bottle.lock" % wineprefix)
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
        logging.info(
            f"Importing wineprefix [{wineprefix['Name']}] in a new bottle …")

        # Hide btn_import to prevent double imports
        widget.set_visible(False)

        # Prepare bottle path for the wine prefix
        bottle_path = "Imported_%s" % wineprefix.get("Name")
        bottle_complete_path = "%s/%s" % (Paths.bottles, bottle_path)

        try:
            os.makedirs(bottle_complete_path, exist_ok=False)
        except:
            logging.error(
                f"Error creating bottle path for wineprefix [{wineprefix['Name']}], aborting.")
            return False

        # Create lockfile in source path
        logging.info("Creating lock file in source path …")
        open('%s/bottle.lock' % wineprefix.get("Path"), 'a').close()

        # Copy wineprefix files in the new bottle
        command = "cp -a %s/* %s/" % (wineprefix.get("Path"),
                                      bottle_complete_path)
        subprocess.Popen(command, shell=True).communicate()

        # Create bottle config
        new_config = Samples.config
        new_config["Name"] = wineprefix["Name"]
        new_config["Runner"] = self.get_latest_runner()
        new_config["Path"] = bottle_path
        new_config["Environment"] = "Custom"
        new_config["Creation_Date"] = str(datetime.now())
        new_config["Update_Date"] = str(datetime.now())

        # Save config
        with open("%s/bottle.yml" % bottle_complete_path,
                  "w") as conf_file:
            yaml.dump(new_config, conf_file, indent=4)
            conf_file.close()

        # Update bottles
        self.update_bottles(silent=True)

        logging.info(
            f"Wineprefix: [{wineprefix['Name']}] successfully imported!")
        return True

    @staticmethod
    def browse_wineprefix(wineprefix: dict) -> bool:
        return Runner().open_filemanager(
            path_type="custom",
            custom_path=wineprefix.get("Path")
        )
