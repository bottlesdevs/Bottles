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

import os, subprocess, json, tarfile, time, shutil, re, urllib.request

from typing import Union, NewType

from gi.repository import Gtk

from glob import glob
from pathlib import Path
from datetime import datetime

from .download import DownloadManager
from .utils import UtilsTerminal, UtilsLogger, UtilsFiles, RunAsync

logging = UtilsLogger()

'''Define custom types for better understanding of the code'''
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)

class BottlesRunner:

    '''Repositories URLs'''
    repository = "https://github.com/lutris/wine/releases"
    repository_api = "https://api.github.com/repos/lutris/wine/releases"
    proton_repository = "https://github.com/GloriousEggroll/proton-ge-custom/releases"
    proton_repository_api = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"
    dxvk_repository = "https://github.com/doitsujin/dxvk/releases"
    dxvk_repository_api = "https://api.github.com/repos/doitsujin/dxvk/releases"
    dependencies_repository = "https://raw.githubusercontent.com/bottlesdevs/dependencies/main/"
    dependencies_repository_index = "%s/index.json" % dependencies_repository
    installers_repository = "https://raw.githubusercontent.com/bottlesdevs/programs/main/"
    installers_repository_index = "%s/index.json" % installers_repository

    '''Local paths'''
    temp_path = "%s/.local/share/bottles/temp" % Path.home()
    runners_path = "%s/.local/share/bottles/runners" % Path.home()
    bottles_path = "%s/.local/share/bottles/bottles" % Path.home()
    dxvk_path = "%s/.local/share/bottles/dxvk" % Path.home()

    '''External managers paths'''
    lutris_path = "%s/Games" % Path.home()
    playonlinux_path = "%s/.PlayOnLinux/wineprefix/" % Path.home()
    bottlesv1_path = "%s/.Bottles" % Path.home()

    '''dxvk overrides'''
    dxvk_dlls = [
        "d3d10core.dll",
        "d3d11.dll",
        "d3d9.dll"
    ]

    '''Component lists'''
    runners_available = []
    dxvk_available = []
    local_bottles = {}
    supported_dependencies = {}
    supported_installers = {}

    '''Bottle configuration sample'''
    sample_configuration = {
        "Name": "",
        "Runner": "",
        "Path": "",
        "Custom_Path": False,
        "Environment": "",
        "Creation_Date": "",
        "Update_Date": "",
        "Versioning": False,
        "State": 0,
        "Parameters": {
            "dxvk": False,
            "dxvk_hud": False,
            "esync": False,
            "fsync": False,
            "aco_compiler": False,
            "discrete_gpu": False,
            "virtual_desktop": False,
            "virtual_desktop_res": "1280x720",
            "pulseaudio_latency": False,
            "environment_variables": "",
            "dll_overrides": ""
        },
        "Installed_Dependencies" : [],
        "Programs" : {}
    }

    '''Environments'''
    environments = {
        "gaming": {
            "Runner": "wine",
            "Parameters": {
                "dxvk": True,
                "esync": True,
                "discrete_gpu": True,
                "pulseaudio_latency": True
            }
        },
        "software": {
            "Runner": "wine",
            "Parameters": {
                "dxvk": True
            }
        }
    }

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.settings = window.settings
        self.utils_conn = window.utils_conn

        self.check_runners(install_latest=False)
        self.check_dxvk(install_latest=False)
        self.fetch_dependencies()
        self.fetch_installers()
        self.check_bottles()
        self.clear_temp()

        self.download_manager = DownloadManager(window)

    '''Performs all checks in one async shot'''
    def async_checks(self):
        self.check_runners_dir()
        self.check_runners()
        self.check_dxvk()
        self.check_bottles()
        self.fetch_dependencies()
        self.fetch_installers()

    def checks(self):
        RunAsync(self.async_checks, None)

    '''Clear temp path'''
    def clear_temp(self, force:bool=False) -> None:
        if self.settings.get_boolean("temp") or force:
            try:
                for f in os.listdir(self.temp_path):
                    os.remove(os.path.join(self.temp_path, f))
                logging.info(_("Temp path cleaned successfully!"))
            except FileNotFoundError:
                logging.error(_("Failed to clear temp path!"))
                self.check_runners_dir()


    '''Update bottles list var and page_list'''
    def update_bottles(self, silent:bool=False) -> None:
        self.check_bottles(silent)
        try:
            self.window.page_list.update_bottles()
        except AttributeError:
            return

    '''Checks if paths exists, else create'''
    def check_runners_dir(self) -> None:
        if not os.path.isdir(self.runners_path):
            logging.info(_("Runners path doens't exist, creating now."))
            os.makedirs(self.runners_path, exist_ok=True)

        if not os.path.isdir(self.bottles_path):
            logging.info(_("Bottles path doens't exist, creating now."))
            os.makedirs(self.bottles_path, exist_ok=True)

        if not os.path.isdir(self.dxvk_path):
            logging.info(_("Dxvk path doens't exist, creating now."))
            os.makedirs(self.dxvk_path, exist_ok=True)

        if not os.path.isdir(self.temp_path):
            logging.info(_("Temp path doens't exist, creating now."))
            os.makedirs(self.temp_path, exist_ok=True)

    '''Get runner updates'''
    def get_runner_updates(self) -> dict:
        updates = {}

        if self.utils_conn.check_connection():
            '''wine'''
            with urllib.request.urlopen(self.repository_api) as url:
                releases = json.loads(url.read().decode())
                for release in [releases[0], releases[1], releases[2]]:
                    tag = release["tag_name"]
                    file = release["assets"][0]["name"]
                    if "%s-x86_64" % tag not in self.runners_available:
                        updates[tag] = file
                    else:
                        logging.warning(
                            _("Latest wine runner: [{0}] already installed.").format(tag))

            '''proton'''
            with urllib.request.urlopen(self.proton_repository_api) as url:
                releases = json.loads(url.read().decode())
                for release in [releases[0], releases[1], releases[2]]:
                    tag = release["tag_name"]
                    file = release["assets"][0]["name"]
                    if "Proton-%s" % tag not in self.runners_available:
                        updates[tag] = file
                    else:
                        logging.warning(
                            _("Latest proton runner: [{0}] already installed.").format(tag))

        '''Notify if the user allows it'''
        if len(updates) == 0:
            self.window.send_notification(_("Download manager"),
                                          _("No runner updates available."),
                                          "software-installed-symbolic")

        return updates

    '''Get dxvk updates'''
    def get_dxvk_updates(self) -> dict:
        updates = {}

        if self.utils_conn.check_connection():
            with urllib.request.urlopen(self.dxvk_repository_api) as url:
                releases = json.loads(url.read().decode())
                for release in [releases[0], releases[1], releases[2]]:
                    tag = release["tag_name"]
                    file = release["assets"][0]["name"]
                    if "dxvk-%s" % tag[1:] not in self.dxvk_available:
                        updates[tag] = file
                    else:
                        logging.warning(
                            _("Latest dxvk: [{0}] already installed.").format(tag))

         '''Notify if the user allows it'''
        if len(updates) == 0:
            self.window.send_notification(_("Download manager"),
                                          _("No dxvk updates available."),
                                          "software-installed-symbolic")

        return updates

    '''Extract a component archive'''
    def extract_component(self, component:str, archive:str) -> True:
        if component in ["runner", "runner:proton"]: path = self.runners_path
        if component == "dxvk": path = self.dxvk_path

        try:
            tar = tarfile.open("%s/%s" % (self.temp_path, archive))
            tar.extractall(path)
            return True
        except EOFError:
            os.remove(os.path.join(self.temp_path, archive))
            shutil.rmtree(os.path.join(path, archive[:-7]))
            logging.error(_("Extraction failed! Archive ends earlier than expected."))
            return False

    '''Download a specific component release'''
    def download_component(self, component:str, tag:str, file:str, rename:bool=False, checksum:bool=False) -> bool:
        if component == "runner": repository = self.repository
        if component == "runner:proton": repository = self.proton_repository
        if component == "dxvk": repository = self.dxvk_repository
        if component == "dependency":
            repository = self.dependencies_repository
            download_url = tag
        else:
            download_url = "%s/download/%s/%s" % (repository, tag, file)

        '''Check if it exists in temp path then don't download'''
        file = rename if rename else file
        if os.path.isfile("%s/%s" % (self.temp_path, file)):
            logging.warning(
                _("File [{0}] already exists in temp, skipping.").format(file))
        else:
            urllib.request.urlretrieve(download_url, "%s/%s" % (self.temp_path, file))

        '''Rename the file if required'''
        if rename:
            logging.info(
                _("Renaming [{0}] to [{1}].").format(file, rename))
            file_path = "%s/%s" % (self.temp_path, rename)
            os.rename("%s/%s" % (self.temp_path, file), file_path)
        else:
            file_path = "%s/%s" % (self.temp_path, file)

        '''Checksums comparison'''
        if checksum:
            checksum = checksum.lower()

            local_checksum = UtilsFiles().get_checksum(file_path)

            if local_checksum != checksum:
                logging.error(
                    _("Downloaded file [{0}] looks corrupted.").format(file))
                logging.error(
                    _("Source checksum: [{0}] downloaded: [{1}]").format(
                        checksum, local_checksum))
                self.window.send_notification(
                    "Bottles",
                    _("Downloaded file {0} looks corrupted. Try again.").format(
                        file),
                    "dialog-error-symbolic",
                    user_settings=False)

                os.remove(file_path)
                return False

        return True

    '''Component installation'''
    def async_install_component(self, args:list) -> None:
        component, tag, file = args

         '''Notify if the user allows it'''
        self.window.send_notification(
            _("Download manager"),
            _("Installing {0} runner …").format(tag),
            "document-save-symbolic")

        if component == "runner": file_name = tag
        if component == "runner:proton": file_name = "proton-%s" % tag
        if component == "dxvk": file_name = "dxvk-%s" % tag

        '''Add entry to download manager'''
        download_entry = self.download_manager.new_download(file_name, False)

        logging.info(_("Installing component: [{0}].").format(tag))

        '''Extract component archive'''
        self.download_component(component, tag, file)
        self.extract_component(component, file)

        '''Empty the component lists and repopulate'''
        if component in ["runner", "runner:proton"]:
            self.runners_available = []
            self.check_runners()

        if component == "dxvk":
            self.dxvk_available = []
            self.check_dxvk()

         '''Notify if the user allows it'''
        self.window.send_notification(
            _("Download manager"),
            _("Component {0} successfully installed!").format(tag),
            "software-installed-symbolic")

        '''Remove entry from download manager'''
        download_entry.remove()

        '''Update component views'''
        if component in ["runner", "runner:proton"]:
            self.window.page_preferences.update_runners()
        if component == "dxvk":
            self.window.page_preferences.update_dxvk()

    def install_component(self, component:str,  tag:str, file:str) -> None:
        if self.utils_conn.check_connection(True):
            RunAsync(self.async_install_component, None, [component, tag, file])

    '''
    Method for deoendency installations
    '''
    def async_install_dependency(self, args:list) -> bool:
        configuration, dependency, widget = args

         '''Notify if the user allows it'''
        self.window.send_notification(
            _("Download manager"),
             _("Installing {0} dependency in bottle {1} …").format(
                 dependency[0], configuration.get("Name")),
             "document-save-symbolic")

        '''Add entry to download manager'''
        download_entry = self.download_manager.new_download(dependency[0], False)

        logging.info(_("Installing dependency: [{0}] in bottle: [{1}].").format(
            dependency[0], configuration.get("Name")))

        '''Get dependency manifest'''
        dependency_manifest = self.fetch_dependency_manifest(
            dependency[0],
            dependency[1]["Category"])

        '''Execute installation steps'''
        for step in dependency_manifest.get("Steps"):
            '''Step type: delete_sys32_dlls'''
            if step["action"] == "delete_sys32_dlls":
                for dll in step["dlls"]:
                    try:
                        logging.info(
                            _("Removing [{0}] from system32 in bottle: [{1}]").format(
                                dll, configuration.get("Name")))
                        os.remove("%s/%s/drive_c/windows/system32/%s" % (
                            self.bottles_path, configuration.get("Name"), dll))
                    except FileNotFoundError:
                        logging.error(
                            _("[{0}] not found in bottle: [{1}], failed removing from system32.").format(
                                dll, configuration.get("Name")))

            '''Step type: install_exe, install_msi'''
            if step["action"] in ["install_exe", "install_msi"]:
                download = self.download_component("dependency",
                                        step.get("url"),
                                        step.get("file_name"),
                                        step.get("rename"),
                                        checksum=step.get("file_checksum"))
                if download:
                    if step.get("rename"):
                        file = step.get("rename")
                    else:
                        file = step.get("file_name")
                    self.run_executable(configuration, "%s/%s" % (
                        self.temp_path, file))
                else:
                    widget.btn_install.set_sensitive(True)
                    return False

        '''Add dependency to bottle configuration'''
        if dependency[0] not in configuration.get("Installed_Dependencies"):
            if configuration.get("Installed_Dependencies"):
                dependencies = configuration["Installed_Dependencies"]+[dependency[0]]
            else:
                dependencies = [dependency[0]]
            self.update_configuration(configuration,
                                      "Installed_Dependencies",
                                      dependencies)

        '''Remove entry from download manager'''
        download_entry.remove()

        '''Hide installation button and show remove button'''
        widget.btn_install.set_visible(False)
        widget.btn_remove.set_visible(True)
        widget.btn_remove.set_sensitive(True)

        return True

    def install_dependency(self, configuration:BottleConfig, dependency:list, widget:Gtk.Widget) -> None:
        if self.utils_conn.check_connection(True):
            RunAsync(self.async_install_dependency, None, [configuration,
                                                           dependency,
                                                           widget])

    def remove_dependency(self, configuration:BottleConfig, dependency:list, widget:Gtk.Widget) -> None:
        logging.info(
            _("Removing dependency: [{0}] from bottle: [{1}] configuration.").format(
                dependency[0], configuration.get("Name")))

        '''Prompt the uninstaller'''
        self.run_uninstaller(configuration)

        '''Remove dependency from bottle configuration'''
        configuration["Installed_Dependencies"].remove(dependency[0])
        self.update_configuration(configuration,
                                  "Installed_Dependencies",
                                  configuration["Installed_Dependencies"])

        '''Show installation button and hide remove button'''
        widget.btn_install.set_visible(True)
        widget.btn_remove.set_visible(False)

    '''Check local runners'''
    def check_runners(self, install_latest:bool=True) -> bool:
        runners = glob("%s/*/" % self.runners_path)
        self.runners_available = []

        for runner in runners:
            self.runners_available.append(runner.split("/")[-2])

        if len(self.runners_available) > 0:
            logging.info(_("Runners found: [{0}]").format(
                ', '.join(self.runners_available)))

        '''
        If there are no locally installed runners, download the latest
        builds for Wine and Proton from the GitHub repositories.
        A very special thanks to Lutris & GloriousEggroll for builds <3!
        '''
        if len(self.runners_available) == 0 and install_latest:
            logging.warning(_("No runners found."))

            '''If connected, fetch runners from repository'''
            if self.utils_conn.check_connection():
                '''Wine'''
                with urllib.request.urlopen(self.repository_api) as url:
                    releases = json.loads(url.read().decode())
                    tag = releases[0]["tag_name"]
                    file = releases[0]["assets"][0]["name"]

                    self.install_component("runner", tag, file)
            else:
                '''Proton
                with urllib.request.urlopen(self.proton_repository_api) as url:
                    releases = json.loads(url.read().decode())
                    tag = releases[0]["tag_name"]
                    file = releases[0]["assets"][0]["name"]

                    self.install_component("runner:proton", tag, file)
                '''
                return False

        '''Sort component lists alphabetically'''
        self.runners_available = sorted(self.runners_available)
        self.dxvk_available = sorted(self.dxvk_available)

        return True

    '''Check local dxvks'''
    def check_dxvk(self, install_latest:bool=True) -> bool:
        dxvk_list = glob("%s/*/" % self.dxvk_path)
        self.dxvk_available = []

        for dxvk in dxvk_list: self.dxvk_available.append(dxvk.split("/")[-2])

        if len(self.dxvk_available) > 0:
            logging.info(_("Dxvk found: [{0}]").format(
                ', '.join(self.dxvk_available)))

        if len(self.dxvk_available) == 0 and install_latest:
            logging.warning(_("No dxvk found."))

            '''If connected, fetch dxvks from repository'''
            if self.utils_conn.check_connection():
                with urllib.request.urlopen(self.dxvk_repository_api) as url:
                    releases = json.loads(url.read().decode())
                    tag = releases[0]["tag_name"]
                    file = releases[0]["assets"][0]["name"]

                    self.install_component("dxvk", tag, file)
            else:
                return False
        return True

    '''Get installed programs'''
    def get_programs(self, configuration:BottleConfig) -> list:
        bottle = "%s/%s" % (self.bottles_path, configuration.get("Path"))
        results =  glob("%s/drive_c/users/*/Start Menu/Programs/**/*.lnk" % bottle,
                        recursive=True)
        results += glob("%s/drive_c/ProgramData/Microsoft/Windows/Start Menu/Programs/**/*.lnk" % bottle,
                        recursive=True)
        installed_programs = []

        '''For any .lnk file, check for executable path'''
        for program in results:
            path = program.split("/")[-1]
            if path not in ["Uninstall.lnk"]:
                executable_path = ""
                try:
                    with open(program, "r",
                              encoding='utf-8',
                              errors='ignore') as lnk:
                        lnk = lnk.read()
                        executable_path = re.search('C:(.*).exe', lnk).group(0)
                        if executable_path.find("ninstall") < 0:
                            path = path.replace(".lnk", "")
                            installed_programs.append([path, executable_path])
                except:
                    logging.error(_("Cannot find executable for [{0}].").format(
                        path))

        return installed_programs


    '''Fetch installers'''
    def fetch_installers(self) -> bool:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen(self.installers_repository_index) as url:
                index = json.loads(url.read())

                for installer in index.items():
                    self.supported_installers[installer[0]] = installer[1]
        else:
            return False
        return True

    '''Fetch installer manifest'''
    def fetch_installer_manifest(self, installer_name:str, installer_category:str, plain:bool=False) -> Union[str, dict, bool]:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen("%s/%s/%s.json" % (
                self.installers_repository,
                installer_category,
                installer_name
            )) as url:
                if plain:
                    return url.read().decode("utf-8")
                else:
                    return json.loads(url.read())

            return False

    '''Fetch dependencies'''
    def fetch_dependencies(self) -> bool:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen(self.dependencies_repository_index) as url:
                index = json.loads(url.read())

                for dependency in index.items():
                    self.supported_dependencies[dependency[0]] = dependency[1]
        else:
            return False
        return True

    '''Fetch dependency manifest'''
    def fetch_dependency_manifest(self, dependency_name:str, dependency_category:str, plain:bool=False) -> Union[str, dict, bool]:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen("%s/%s/%s.json" % (
                self.dependencies_repository,
                dependency_category,
                dependency_name
            )) as url:
                if plain:
                    return url.read().decode("utf-8")
                else:
                    return json.loads(url.read())

            return False

    '''Check local bottles'''
    def check_bottles(self, silent:bool=False) -> None:
        bottles = glob("%s/*/" % self.bottles_path)

        '''
        For each bottle add the path name to the `local_bottles` variable
        and append the configuration
        '''
        for bottle in bottles:
            bottle_name_path = bottle.split("/")[-2]
            try:
                configuration_file = open('%s/bottle.json' % bottle)
                configuration_file_json = json.load(configuration_file)
                configuration_file.close()

                missing_keys = self.sample_configuration.keys() - configuration_file_json.keys()
                for key in missing_keys:
                    logging.warning(
                        _("Key: [{0}] not in bottle: [{1}] configuration, updating.").format(
                            key, bottle.split("/")[-2]))
                    self.update_configuration(configuration_file_json,
                                              key,
                                              self.sample_configuration[key])

                missing_parameters_keys = self.sample_configuration["Parameters"].keys() - configuration_file_json["Parameters"].keys()
                for key in missing_parameters_keys:
                    logging.warning(
                        _("Key: [{0}] not in bottle: [{1}] configuration Parameters, updating.").format(
                            key, bottle.split("/")[-2]))
                    self.update_configuration(configuration_file_json,
                                              key,
                                              self.sample_configuration["Parameters"][key],
                                              scope="Parameters")
                self.local_bottles[bottle_name_path] = configuration_file_json

            except FileNotFoundError:
                new_configuration_json = self.sample_configuration
                new_configuration_json["Broken"] = True
                new_configuration_json["Name"] = bottle_name_path
                new_configuration_json["Environment"] = "Undefined"
                self.local_bottles[bottle_name_path] = new_configuration_json
                continue


        if len(self.local_bottles) > 0 and not silent:
            logging.info(_("Bottles found: %s") % ', '.join(self.local_bottles))

    '''Get bottle path by configuration'''
    def get_bottle_path(self, configuration:BottleConfig) -> str:
        if configuration.get("Custom_Path"):
            return configuration.get("Path")
        return "%s/%s" % (self.bottles_path, configuration.get("Path"))

    '''Update parameters in bottle configuration'''
    def update_configuration(self, configuration:BottleConfig, key:str, value:str, scope:str="") -> dict:
        logging.info(
            _("Setting Key: [{0}] to [{1}] for bottle: [{2}] …").format(
                key, value, configuration.get("Name")))

        bottle_complete_path = self.get_bottle_path(configuration)

        if scope != "":
            configuration[scope][key] = value
        else:
            configuration[key] = value

        with open("%s/bottle.json" % bottle_complete_path,
                  "w") as configuration_file:
            json.dump(configuration, configuration_file, indent=4)
            configuration_file.close()

        self.update_bottles(silent=True)

        '''Update Update_Date in configuration'''
        configuration["Update_Date"] = str(datetime.now())
        return configuration

    '''Create new wineprefix'''
    def async_create_bottle(self, args:list) -> None:
        logging.info(_("Creating the wineprefix …"))

        name, environment, path, runner, versioning = args

        if not runner: runner = self.runners_available[0]
        runner_name = runner
        update_output = self.window.page_create.update_output

        '''If runner is proton, files are located to the dist path'''
        if runner.startswith("Proton"): runner = "%s/dist" % runner

        '''If there are no local runners and dxvks, install them'''
        if 0 in [len(self.runners_available), len(self.dxvk_available)]:
            update_output( _("Runner and/or dxvk not found, installing latest version …"))
            self.window.page_preferences.set_dummy_runner()
            self.window.show_runners_preferences_view()
            return self.async_checks()

        '''Set UI to not usable'''
        self.window.set_usable_ui(False)

        '''Define bottle parameters'''
        bottle_name = name
        bottle_name_path = bottle_name.replace(" ", "-")

        if path == "":
            bottle_custom_path = False
            bottle_complete_path = "%s/%s" % (self.bottles_path, bottle_name_path)
        else:
            bottle_custom_path = True
            bottle_complete_path = path

        '''Make progressbar pulsing'''
        RunAsync(self.window.page_create.pulse, None)

        '''Execute wineboot'''
        update_output( _("The wine configuration is being updated …"))
        command = "WINEPREFIX={path} WINEARCH=win64 {runner} wineboot".format(
            path = bottle_complete_path,
            runner = "%s/%s/bin/wine64" % (self.runners_path, runner)
        )
        subprocess.Popen(command, shell=True).communicate()
        update_output(_("Wine configuration updated!"))
        time.sleep(1)

        '''Generate bottle configuration file'''
        logging.info(_("Generating Bottle configuration file …"))
        update_output( _("Generating Bottle configuration file …"))

        configuration = self.sample_configuration
        configuration["Name"] = bottle_name
        configuration["Runner"] = runner_name
        if path == "":
            configuration["Path"] = bottle_name_path
        else:
            configuration["Path"] = bottle_complete_path
        configuration["Custom_Path"] = bottle_custom_path
        configuration["Environment"] = environment
        configuration["Creation_Date"] = str(datetime.now())
        configuration["Update_Date"] = str(datetime.now())
        if versioning: configuration["Versioning"] = True

        '''Apply environment configuration'''
        logging.info(
            _("Applying environment: [{0}] …").format(environment))
        update_output(_("Applying environment: {0} …").format(environment))
        if environment != "Custom":
            environment_parameters = self.environments[environment.lower()]["Parameters"]
            for parameter in configuration["Parameters"]:
                if parameter in environment_parameters:
                    configuration["Parameters"][parameter] = environment_parameters[parameter]

        time.sleep(1)

        '''Save bottle configuration'''
        with open("%s/bottle.json" % bottle_complete_path,
                  "w") as configuration_file:
            json.dump(configuration, configuration_file, indent=4)
            configuration_file.close()

        time.sleep(5)

        '''Perform dxvk installation if configured'''
        if configuration["Parameters"]["dxvk"]:
            logging.info(_("Installing dxvk …"))
            update_output( _("Installing dxvk …"))
            self.install_dxvk(configuration)

        time.sleep(1)

        '''Create first state if versioning enabled'''
        if versioning:
            logging.info(_("Creating versioning state 0 …"))
            update_output( _("Creating versioning state 0 …"))
            self.async_create_bottle_state([configuration, "First boot"])

        '''Set status created and UI usability'''
        logging.info(_("Bottle: [{0}] successfully created!").format(
            bottle_name))
        update_output(_("Your new bottle: {0} is now ready!").format(
            bottle_name))
        self.window.page_create.set_status("created")
        self.window.set_usable_ui(True)

        '''Update bottles'''
        self.local_bottles = {}
        self.check_bottles()

    def create_bottle(self, name, environment:str, path:str=False, runner:RunnerName=False, versioning:bool=False) -> None:
        RunAsync(self.async_create_bottle, None, [name,
                                                  environment,
                                                  path,
                                                  runner,
                                                  versioning])

    '''Get latest installed runner'''
    def get_latest_runner(self, runner_type:RunnerType="wine") -> list:
        if runner_type in ["", "wine"]:
            latest_runner = [idx for idx in self.runners_available if idx.lower().startswith("lutris")][0]
        else:
            latest_runner = [idx for idx in self.runners_available if idx.lower().startswith("proton")][0]
        return latest_runner

    '''Get human size by a float'''
    @staticmethod
    def get_human_size(size:float) -> str:
        for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
            if abs(size) < 1024.0:
                return "%3.1f%s%s" % (size, unit, 'B')
            size /= 1024.0

        return "%.1f%s%s" % (size, 'Yi', 'B')

    '''Get path size'''
    def get_path_size(self, path:str, human:bool=True) -> Union[str, float]:
        path = Path(path)
        size = sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())

        if human: return self.get_human_size(size)

        return size

    '''Get disk size'''
    def get_disk_size(self, human:bool=True) -> dict:
        '''TODO: disk should be taken from configuration Path'''
        disk_total, disk_used, disk_free = shutil.disk_usage('/')

        if human:
            disk_total = self.get_human_size(disk_total)
            disk_used = self.get_human_size(disk_used)
            disk_free = self.get_human_size(disk_free)

        return {
            "total": disk_total,
            "used": disk_used,
            "free": disk_free,
        }

    '''Get bottle path size'''
    def get_bottle_size(self, configuration:BottleConfig, human:bool=True) -> Union[str, float]:
        path = configuration.get("Path")

        if not configuration.get("Custom_Path"):
            path = "%s/%s" % (self.bottles_path, path)

        return self.get_path_size(path, human)

    '''Delete a wineprefix'''
    def async_delete_bottle(self, args:list) -> bool:
        logging.info(_("Deleting a bottle …"))

        configuration = args[0]

        '''Delete path with all files'''
        path = configuration.get("Path")

        if path != "":
            if not configuration.get("Custom_Path"):
                path = "%s/%s" % (self.bottles_path, path)

            shutil.rmtree(path)
            logging.info(_("Successfully deleted bottle in path: [{0}]").format(
                path))
            return True
        else:
            logging.error(_("Empty path found, failing to avoid disasters."))
            return False

    def delete_bottle(self, configuration:BottleConfig) -> None:
        RunAsync(self.async_delete_bottle, None, [configuration])

    ''' Repair a bottle generating a new configuration'''
    def repair_bottle(self, configuration:BottleConfig) -> bool:
        logging.info(_("Trying to repair the bottle: [{0}] …").format(
            configuration.get("Name")))

        bottle_complete_path = "%s/%s" % (self.bottles_path,
                                          configuration.get("Name"))

        '''Create new configuration with path as name and Custom environment '''
        new_configuration = self.sample_configuration
        new_configuration["Name"] = configuration.get("Name")
        new_configuration["Runner"] = self.runners_available[0]
        new_configuration["Path"] = configuration.get("Name")
        new_configuration["Environment"] = "Custom"
        new_configuration["Creation_Date"] = str(datetime.now())
        new_configuration["Update_Date"] = str(datetime.now())
        del new_configuration["Broken"]

        try:
            with open("%s/bottle.json" % bottle_complete_path,
                      "w") as configuration_file:
                json.dump(new_configuration, configuration_file, indent=4)
                configuration_file.close()
        except:
            return False

        '''Execute wineboot in bottle to generate missing files'''
        self.run_wineboot(new_configuration)

        '''Update bottles'''
        self.update_bottles()
        return True

    '''Get running wine processes'''
    @staticmethod
    def get_running_processes() -> list:
        processes = []
        command = "ps -eo pid,pmem,pcpu,stime,time,cmd | grep wine | tr -s ' ' '|'"
        pids = subprocess.check_output(['bash', '-c', command]).decode("utf-8")

        for pid in pids.split("\n"):
            process_data = pid.split("|")
            if len(process_data) >= 6 and "grep" not in process_data:
                processes.append({
                    "pid": process_data[1],
                    "pmem": process_data[2],
                    "pcpu": process_data[3],
                    "stime": process_data[4],
                    "time": process_data[5],
                    "cmd": process_data[6]
                })

        return processes

    '''Add key from register'''
    def reg_add(self, configuration:BottleConfig, key:str, value:str, data:str) -> None:
        logging.info(
            _("Adding Key: [{0}] with Value: [{1}] and Data: [{2}] in register bottle: {3}").format(
                key, value, data, configuration.get("Name")))

        self.run_command(configuration, "reg add '%s' /v %s /d %s /f" % (
            key, value, data))

    '''Remove key from register'''
    def reg_delete(self, configuration:BottleConfig, key:str, value:str) -> None:
        logging.info(
            _("Removing Value: [{0}] for Key: [{1}] in register bottle: {2}").format(
                key, value, configuration.get("Name")))

        self.run_command(configuration, "reg delete '%s' /v %s /f" % (
            key, value))

    '''
    Install dxvk using official script
    TODO: A good task for the future is to use the built-in methods
    to install the new dlls and register the override for dxvk.
    '''
    def install_dxvk(self, configuration:BottleConfig, remove:bool=False) -> bool:
        logging.info(_("Installing dxvk for bottle: [{0}].").format(
            configuration.get("Name")))

        option = "uninstall" if remove else "install"

        command = 'WINEPREFIX="{path}" PATH="{runner}:$PATH" {dxvk_setup} {option}'.format (
            path = "%s/%s" % (self.bottles_path, configuration.get("Path")),
            runner = "%s/%s/bin" % (self.runners_path, configuration.get("Runner")),
            dxvk_setup = "%s/%s/setup_dxvk.sh" % (self.dxvk_path, self.dxvk_available[0]),
            option = option)

        return subprocess.Popen(command, shell=True).communicate()

    '''Remove dxvk using official script'''
    def remove_dxvk(self, configuration:BottleConfig) -> None:
        logging.info(_("Removing dxvk for bottle: [{0}].").format(
            configuration.get("Name")))

        self.install_dxvk(configuration, remove=True)

    '''Override dlls in system32/syswow64 paths'''
    def dll_override(self, configuration:BottleConfig, arch:str, dlls:list, source:str, revert:bool=False) -> bool:
        arch = "system32" if arch == 32 else "syswow64"
        path = "%s/%s/drive_c/windows/%s" % (self.bottles_path,
                                             configuration.get("Path"),
                                             arch)
        '''Restore dll from backup'''
        try:
            if revert:
                for dll in dlls:
                    shutil.move("%s/%s.back" % (path, dll), "%s/%s" % (path, dll))
            else:
                '''
                Backup old dlls and install new one
                '''
                for dll in dlls:
                    shutil.move("%s/%s" % (path, dll), "%s/%s.old" % (path, dll))
                    shutil.copy("%s/%s" % (source, dll), "%s/%s" % (path, dll))
        except:
            return False
        return True

    '''Toggle virtual desktop for a bottle'''
    def toggle_virtual_desktop(self, configuration:BottleConfig, state:bool, resolution:str="800x600") -> None:
        key = "HKEY_CURRENT_USER\\Software\\Wine\\Explorer\\Desktops"
        if state:
            self.reg_add(configuration, key, "Default", resolution)
        else:
            self.reg_delete(configuration, key, "Default")

    '''Run wine executables/programs in a bottle'''
    def run_executable(self, configuration:BottleConfig, file_path:str, arguments:str=False) -> None:
        logging.info(_("Running an executable on the wineprefix …"))

        if "msi" in file_path.split("."):
            command = "msiexec /i '%s'" % file_path
        else:
            command = "'%s'" % file_path

        if arguments: command = "%s %s" % (command, arguments)

        RunAsync(self.run_command, None, configuration, command)

    def run_wineboot(self, configuration:BottleConfig) -> None:
        logging.info(_("Running wineboot on the wineprefix …"))
        RunAsync(self.run_command, None, configuration, "wineboot -u")

    def run_winecfg(self, configuration:BottleConfig) -> None:
        logging.info(_("Running winecfg on the wineprefix …"))
        RunAsync(self.run_command, None, configuration, "winecfg")

    def run_winetricks(self, configuration:BottleConfig) -> None:
        logging.info(_("Running winetricks on the wineprefix …"))
        RunAsync(self.run_command, None, configuration, "winetricks")

    def run_debug(self, configuration:BottleConfig) -> None:
        logging.info(_("Running a debug console on the wineprefix …"))
        RunAsync(self.run_command, None, configuration, "winedbg", True)

    def run_cmd(self, configuration:BottleConfig) -> None:
        logging.info(_("Running a CMD on the wineprefix …"))
        RunAsync(self.run_command, None, configuration, "wineconsole cmd")

    def run_taskmanager(self, configuration:BottleConfig) -> None:
        logging.info(_("Running a Task Manager on the wineprefix …"))
        RunAsync(self.run_command, None, configuration, "taskmgr")

    def run_controlpanel(self, configuration:BottleConfig) -> None:
        logging.info(_("Running a Control Panel on the wineprefix …"))
        RunAsync(self.run_command, None, configuration, "control")

    def run_uninstaller(self, configuration:BottleConfig) -> None:
        logging.info(_("Running an Uninstaller on the wineprefix …"))
        RunAsync(self.run_command, None, configuration, "uninstaller")

    def run_regedit(self, configuration:BottleConfig) -> None:
        logging.info(_("Running a Regedit on the wineprefix …"))
        RunAsync(self.run_command, None, configuration, "regedit")

    '''Execute command in a bottle'''
    def run_command(self, configuration:BottleConfig, command:str, terminal:bool=False) -> bool:
        path = configuration.get("Path")
        runner = configuration.get("Runner")

        '''If runner is proton then set path to /dist'''
        if runner.startswith("Proton"):
            runner = "%s/dist" % runner

        if not configuration.get("Custom_Path"):
            path = "%s/%s" % (self.bottles_path, path)

        '''Check for executable args from bottle configuration'''
        environment_vars = []
        dll_overrides = []
        parameters = configuration["Parameters"]

        if parameters["dll_overrides"]:
            dll_overrides.append(parameters["dll_overrides"])

        if parameters["environment_variables"]:
            environment_vars.append(parameters["environment_variables"])

        if parameters["dxvk"]:
            dll_overrides.append("d3d11,dxgi=n")
            environment_vars.append("DXVK_STATE_CACHE_PATH='%s'" % path)
            environment_vars.append("STAGING_SHARED_MEMORY=1")
            environment_vars.append("__GL_DXVK_OPTIMIZATIONS=1")
            environment_vars.append("__GL_SHADER_DISK_CACHE=1")
            environment_vars.append("__GL_SHADER_DISK_CACHE_PATH='%s'" % path)

        if parameters["dxvk_hud"]:
            environment_vars.append("DXVK_HUD='devinfo,memory,drawcalls,fps,version,api,compiler'")
        else:
            environment_vars.append("DXVK_HUD='compiler'")

        if parameters["esync"]:
            environment_vars.append("WINEESYNC=1 WINEDEBUG=+esync")

        if parameters["fsync"]:
            environment_vars.append("WINEFSYNC=1")

        if parameters["aco_compiler"]:
            environment_vars.append("RADV_PERFTEST=aco")

        if parameters["discrete_gpu"]:
            if "nvidia" in subprocess.Popen(
                "lspci | grep 'VGA'",
                stdout=subprocess.PIPE,
                shell=True).communicate()[0].decode("utf-8"):
                environment_vars.append("__NV_PRIME_RENDER_OFFLOAD=1")
                environment_vars.append("__GLX_VENDOR_LIBRARY_NAME='nvidia'")
                environment_vars.append("__VK_LAYER_NV_optimus='NVIDIA_only'")
            else:
                environment_vars.append("DRI_PRIME=1")

        if parameters["pulseaudio_latency"]:
            environment_vars.append("PULSE_LATENCY_MSEC=60")

        environment_vars.append("WINEDLLOVERRIDES='%s'" % ",".join(dll_overrides))
        environment_vars = " ".join(environment_vars)

        command = "WINEPREFIX={path} WINEARCH=win64 {env} {runner} {command}".format(
            path = path,
            env = environment_vars,
            runner = "%s/%s/bin/wine64" % (self.runners_path, runner),
            command = command
        )

        if terminal:
            return UtilsTerminal(command)

        return subprocess.Popen(command, shell=True).communicate()

    '''Send status to a bottle'''
    def send_status(self, configuration:BottleConfig, status:str) -> None:
        logging.info(
            _("Sending Status: [{0}] to the wineprefix …").format(status))

        available_status = {
            "shutdown": "-s",
            "reboot": "-r",
            "kill": "-k"
        }

        option = available_status[status]
        bottle_name = configuration.get("Name")

        self.run_command(configuration, "wineboot %s" % option)

         '''Notify if the user allows it'''
        self.window.send_notification(
            "Bottles",
            _("{0} completed for {1}.").format(status, bottle_name
            ), "applications-system-symbolic")

    '''Open file manager in different paths'''
    def open_filemanager(self, configuration:BottleConfig=dict, path_type:str="bottle", runner:str="", dxvk:str="", custom_path:str="") -> bool:
        logging.info(_("Opening the file manager in the path …"))

        if path_type == "bottle":
            path = "%s/%s/drive_c" % (self.bottles_path,
                                      configuration.get("Path"))

        if path_type == "runner" and runner != "":
            path = "%s/%s" % (self.runners_path, runner)

        if path_type == "dxvk" and dxvk != "":
            path = "%s/%s" % (self.dxvk_path, dxvk)

        if path_type == "custom" and custom_path != "":
            path = custom_path

        command = "xdg-open %s" % path
        return subprocess.Popen(command, shell=True).communicate()

    '''
    Methods for search and import wineprefixes from other managers
    '''
    def search_wineprefixes(self) -> list:
        importer_wineprefixes = []

        '''Search wine prefixes in external managers paths'''
        lutris_results = glob("%s/*/" % self.lutris_path)
        playonlinux_results = glob("%s/*/" % self.playonlinux_path)
        bottlesv1_results = glob("%s/*/" % self.bottlesv1_path)

        results = lutris_results + playonlinux_results + bottlesv1_results

        '''Count results'''
        is_lutris = len(lutris_results)
        is_playonlinux = is_lutris + len(playonlinux_results)
        i=1

        for wineprefix in results:
            wineprefix_name = wineprefix.split("/")[-2]

            '''Identify manager by index'''
            if i <= is_lutris:
                wineprefix_manager = "Lutris"
            elif i <=  is_playonlinux:
                wineprefix_manager = "PlayOnLinux"
            else:
                wineprefix_manager = "Bottles v1"

            '''Check the drive_c path exists'''
            if os.path.isdir("%s/drive_c" % wineprefix):
                wineprefix_lock = os.path.isfile("%s/bottle.lock" % wineprefix)
                importer_wineprefixes.append(
                    {
                        "Name": wineprefix_name,
                        "Manager": wineprefix_manager,
                        "Path": wineprefix,
                        "Lock": wineprefix_lock
                    })
            i+=1

        logging.info("Found %s wineprefixes .." % len(importer_wineprefixes))
        return importer_wineprefixes

    def import_wineprefix(self, wineprefix:dict, widget:Gtk.Widget) -> bool:
        logging.info(
            _("Importing wineprefix [{0}] in a new bottle …").format(
                wineprefix.get("Name")))

        '''Hide btn_import to prevent double imports'''
        widget.set_visible(False)

        '''Prepare bottle path for the wine prefix'''
        bottle_path = "Imported_%s" % wineprefix.get("Name")
        bottle_complete_path = "%s/%s" % (self.bottles_path, bottle_path)

        try:
            os.makedirs(bottle_complete_path, exist_ok=False)
        except:
            logging.error(
                _("Error creating the bottle path for wineprefix [{0}]. Aborting.").format(
                    wineprefix.get("Name")))
            return False

        '''Create lockfile in source path'''
        logging.info(_("Creating lock file in source path …"))
        open('%s/bottle.lock' % wineprefix.get("Path"), 'a').close()

        '''Copy wineprefix files in the new bottle'''
        command = "cp -a %s/* %s/" % (wineprefix.get("Path"), bottle_complete_path)
        subprocess.Popen(command, shell=True).communicate()

        '''Create bottle configuration'''
        new_configuration = self.sample_configuration
        new_configuration["Name"] = wineprefix["Name"]
        new_configuration["Runner"] = self.get_latest_runner()
        new_configuration["Path"] = bottle_path
        new_configuration["Environment"] = "Custom"
        new_configuration["Creation_Date"] = str(datetime.now())
        new_configuration["Update_Date"] = str(datetime.now())

        '''Save configuration'''
        with open("%s/bottle.json" % bottle_complete_path,
                  "w") as configuration_file:
            json.dump(new_configuration, configuration_file, indent=4)
            configuration_file.close()

        '''Update bottles'''
        self.update_bottles(silent=True)

        '''Notify if the user allows it'''
        self.window.send_notification(
            _("Importer"),
            _("Wineprefix {0} successfully imported!").format(
                wineprefix["Name"]), "software-installed-symbolic")


        logging.info(
            _("Wineprefix: [{0}] successfully imported!").format(
                wineprefix["Name"]))
        return True


    def browse_wineprefix(self, wineprefix:dict) -> bool:
        return self.open_filemanager(path_type="custom",
                                     custom_path=wineprefix.get("Path"))

    '''Create new bottle state'''
    def async_create_bottle_state(self, args:list) -> bool:
        configuration, comment = args

        logging.info("Creating new state for bottle: [{0}] …".format(
            configuration.get("Name")))

        bottle_path = self.get_bottle_path(configuration)
        first = False if os.path.isdir('%s/states/' % bottle_path) else True

        '''Set UI to not usable'''
        self.window.set_usable_ui(False)

        '''List all bottle files'''
        current_index = self.get_bottle_index(configuration)

        '''If it is not the first state, compare files with the previous one'''
        if not first:
            states_file = open('%s/states/states.json' % bottle_path)
            states_file_json = json.load(states_file)
            states_file.close()

            state_index_file = open('%s/states/%s/index.json' % (
                bottle_path, str(configuration.get("State"))))
            state_index = json.load(state_index_file)
            state_index_file.close()
            state_index_files = state_index["Additions"]+\
                                state_index["Removed"]+\
                                state_index["Changes"]

            state_temp_checksums = [f["checksum"] for f in state_index_files]
            state_temp_files = [tuple([f["file"],f["checksum"]])  for f in state_index_files]
            current_temp_files = [tuple([f["file"],f["checksum"]])  for f in current_index["Files"]]
            additions = set(current_temp_files) - set(state_temp_files)
            removed = set(state_temp_files) - set(current_temp_files)

            new_state_index = {
                "Update_Date": str(datetime.now()),
                "Additions": [],
                "Removed": [],
                "Changes": []
            }

            for file in additions:
                new_state_index["Additions"].append({
                    "file": file[0],
                    "checksum": file[1]
                })

            for file in removed:
                new_state_index["Removed"].append({
                    "file": file[0],
                    "checksum": file[1]
                })

            for file in current_index["Files"]:
                if file["checksum"] not in state_temp_checksums:
                    new_state_index["Changes"].append({
                        "file": file["file"],
                        "checksum": file["checksum"]
                    })

            state_id = str(len(states_file_json.get("States")))
        else:
            new_state_index = {
                "Update_Date": str(datetime.now()),
                "Additions": current_index["Files"],
                "Removed": [],
                "Changes": []
            }
            state_id = "0"

        state_path = "%s/states/%s" % (bottle_path, state_id)

        '''Add entry to download manager'''
        download_entry = self.download_manager.new_download(
            _("Generating state {0} for {1}").format(
                state_id, configuration.get("Name")), False)

        try:
            '''Make state structured path'''
            os.makedirs("%s/states/%s/drive_c" % (bottle_path, state_id), exist_ok=True)

            '''Save index.json with state edits'''
            with open("%s/index.json" % (state_path),
                      "w") as state_index_file:
                json.dump(new_state_index, state_index_file, indent=4)
                state_index_file.close()

            '''Save files.json with bottle files'''
            with open("%s/files.json" % (state_path),
                      "w") as state_files_file:
                json.dump(current_index, state_files_file, indent=4)
                state_files_file.close()
        except:
            return False

        '''Copy indexed files in the new state path'''
        for file in current_index["Files"]:
            os.makedirs("{0}/drive_c/{1}".format(
                state_path,
                "/".join(file["file"].split("/")[:-1])), exist_ok=True)
            source = "{0}/drive_c/{1}".format(bottle_path, file["file"])
            target = "{0}/drive_c/{1}".format(state_path, file["file"])
            shutil.copyfile(source, target)

        time.sleep(5)

        '''Update the states.json file'''
        new_state = {
			"Creation_Date": str(datetime.now()),
			"Comment": comment,
			# "Files": [file["file"] for file in current_index["Files"]]
		}

        if not first:
            new_state_file = {
                "Update_Date": str(datetime.now()),
                "States": states_file_json.get("States")
            }
            new_state_file["States"][state_id] = new_state
        else:
            new_state_file = {
                "Update_Date": str(datetime.now()),
                "States": {"0": new_state}
            }

        try:
            with open('%s/states/states.json' % bottle_path, "w") as states_file:
                json.dump(new_state_file, states_file, indent=4)
                states_file.close()
        except:
            return False

        '''Create new index.json in the states root'''
        try:
            with open('%s/states/index.json' % bottle_path,
                      "w") as current_index_file:
                json.dump(current_index, current_index_file, indent=4)
                current_index_file.close()
        except:
            return False

        '''Update State in bottle configuration'''
        self.update_configuration(configuration, "State", state_id)

        logging.info("New state [{0}] created successfully!".format(state_id))

        '''Remove entry from download manager'''
        download_entry.remove()

        '''Update states'''
        self.window.page_details.update_states()

        '''Update bottles'''
        time.sleep(2)
        self.update_bottles()

        '''Set UI to usable again'''
        self.window.set_usable_ui(True)

        return True

    def create_bottle_state(self, configuration:BottleConfig, comment:str="Not commented") -> None:
        RunAsync(self.async_create_bottle_state, None, [configuration, comment])

    '''Get edits for a state'''
    def get_bottle_state_edits(self, configuration:BottleConfig, state_id:str, plain:bool=False) -> dict:
        bottle_path = self.get_bottle_path(configuration)

        try:
            file = open('%s/states/%s/index.json' % (bottle_path, state_id))
            files = file.read() if plain else json.loads(file.read())
            file.close()
            return files
        except:
            return {}

    '''Get files for a state'''
    def get_bottle_state_files(self, configuration:BottleConfig, state_id:str, plain:bool=False) -> dict:
        bottle_path = self.get_bottle_path(configuration)

        try:
            file = open('%s/states/%s/files.json' % (bottle_path, state_id))
            files = file.read() if plain else json.loads(file.read())
            file.close()
            return files
        except:
            return {}

    '''Get all bottle files'''
    def get_bottle_index(self, configuration:BottleConfig):
        bottle_path = self.get_bottle_path(configuration)

        current_index = {
            "Update_Date": str(datetime.now()),
            "Files":[]
        }
        for file in glob("%s/drive_c/**" % bottle_path, recursive=True):
            if not os.path.isfile(file): continue
            if file[len(bottle_path)+9:].split("/")[0] in ["users"]: continue

            current_index["Files"].append({
                "file": file[len(bottle_path)+9:],
                "checksum": UtilsFiles().get_checksum(file)})
        return current_index

    '''Set state for a bottle'''
    def set_bottle_state(self, configuration:BottleConfig, state_id:str) -> bool:
        bottle_path = self.get_bottle_path(configuration)

        logging.info(_("Restoring to state: [{0}]").format(state_id))

        '''Set UI to not usable'''
        self.window.set_usable_ui(False)

        '''Get indexes'''
        bottle_index = self.get_bottle_index(configuration)
        state_index = self.get_bottle_state_files(configuration, state_id)

        search_sources = list(range(int(state_id)+1))
        search_sources.reverse()

        '''Check for removed and chaged files'''
        remove_files = []
        edit_files = []
        for file in bottle_index.get("Files"):
            if file["file"] not in [file["file"] for file in state_index.get("Files")]:
                remove_files.append(file)
            elif file["checksum"] not in [file["checksum"] for file in state_index.get("Files")]:
                edit_files.append(file)
        logging.info(_("[{0}] files to remove.").format(len(remove_files)))
        logging.info(_("[{0}] files to replace.").format(len(edit_files)))

        '''Check for new files'''
        add_files = []
        for file in state_index.get("Files"):
            if file["file"] not in [file["file"] for file in bottle_index.get("Files")]:
                add_files.append(file)
        logging.info(_("[{0}] files to add.").format(len(add_files)))

        '''Perform file updates'''
        for file in remove_files:
            os.remove("%s/drive_c/%s" % (bottle_path, file["file"]))

        for file in add_files:
            for i in search_sources:
                source = "%s/states/%s/drive_c/%s" % (bottle_path, str(i), file["file"])
                if os.path.isfile(source): break
            target = "%s/drive_c/%s" % (bottle_path, file["file"])
            shutil.copyfile(source, target)

        for file in edit_files:
            for i in search_sources:
                source = "%s/states/%s/drive_c/%s" % (bottle_path, str(i), file["file"])
                if os.path.isfile(source):
                    checksum = UtilsFiles().get_checksum(source)
                    if file["checksum"] == checksum: break
            target = "%s/drive_c/%s" % (bottle_path, file["file"])
            shutil.copyfile(source, target)

        '''Update State in bottle configuration'''
        self.update_configuration(configuration, "State", state_id)

        '''Update states'''
        self.window.page_details.update_states()

        '''Update bottles'''
        time.sleep(2)
        self.update_bottles()

        '''Set UI to usable again'''
        self.window.set_usable_ui(False)

        return True

    def list_bottle_states(self, configuration:BottleConfig) -> dict:
        bottle_path = self.get_bottle_path(configuration)

        try:
            states_file = open('%s/states/states.json' % bottle_path)
            states_file_json = json.load(states_file)
            states_file.close()
            states = states_file_json.get("States")

            logging.info(
                "Found [{0}] states for bottle: [{1}]".format(
                len(states), configuration.get("Name")))
            return states
        except:
            logging.error(
                "Cannot find states.json file for bottle: [{0}]".format(
                configuration.get("Name")))

            return {}

    '''Make a bottle backup'''
    def async_backup_bottle(self, args:list) -> bool:
        configuration, scope, path = args

        '''Set UI to not usable'''
        self.window.set_usable_ui(False)

        if scope == "configuration":
            '''Backup type: configuration'''
            logging.info(
                _("Backuping configuration: [{0}] in [{1}]").format(
                    configuration.get("Name"), path))

            try:
                with open(path, "w") as configuration_backup:
                    json.dump(configuration, configuration_backup, indent=4)
                    configuration_backup.close()
                backup_created = True
            except:
                backup_created = False

        else:
            '''Backup type: full'''
            logging.info(
                _("Backuping bottle: [{0}] in [{1}]").format(
                    configuration.get("Name"), path))

            '''Add entry to download manager'''
            download_entry = self.download_manager.new_download(
                _("Backup {0}").format(configuration.get("Name")), False)

            bottle_path = self.get_bottle_path(configuration)

            try:
                '''Create the archive'''
                with tarfile.open(path, "w:gz") as archive_backup:
                    for root, dirs, files in os.walk(bottle_path):
                        for file in files:
                            archive_backup.add(os.path.join(root, file))
                    archive_backup.close()
                backup_created = True
            except:
                backup_created = False

            '''Remove entry from download manager'''
            download_entry.remove()

        if backup_created:
            logging.info(_("Backup saved in path: {0}.").format(path))

             '''Notify if the user allows it'''
            self.window.send_notification(
                "Backup",
                _("Your backup for {0} is ready!").format(
                    configuration.get("Name")
                ), "software-installed-symbolic")
            return True
        else:
            logging.error(_("Failed to save backup in path: {0}.").format(path))

             '''Notify if the user allows it'''
            self.window.send_notification(
                "Backup",
                _("Failed to create backup for {0}!").format(
                    configuration.get("Name")
                ), "dialog-error-symbolic")

        '''Set UI to usable again'''
        self.window.set_usable_ui(False)

        return False

    def backup_bottle(self, configuration:BottleConfig, scope:str, path:str) -> None:
        RunAsync(self.async_backup_bottle, None, [configuration, scope, path])

    def async_import_backup_bottle(self, args:list) -> bool:
        scope, path = args

        if scope == "configuration":
            backup_name = path.split("/")[-1].split(".")[-2]
            backup_imported = False
        else:
            backup_name = path.split("/")[-1].split(".")[-3]

            if backup_name.lower().startswith("backup_"):
                backup_name = backup_name[7:]

            '''Add entry to download manager'''
            download_entry = self.download_manager.new_download(
                _("Importing backup: {0}").format(backup_name), False)

            try:
                archive = tarfile.open(path)
                archive.extractall("%s/%s" % (self.bottles_path, backup_name))
                backup_imported = True
            except:
                backup_imported = False

            '''Remove entry from download manager'''
            download_entry.remove()

        if backup_imported:
            logging.info(
                _("Backup: [{0}] imported successfully.").format(path))

            '''Update bottles'''
            self.update_bottles()

             '''Notify if the user allows it'''
            self.window.send_notification(
                "Backup",
                _("Your backup {0} was imported successfully.!").format(
                    backup_name), "software-installed-symbolic")
            return True
        else:
            logging.error(_("Failed importing backup: [{0}]").format(
                backup_name))

             '''Notify if the user allows it'''
            self.window.send_notification(
                "Backup",
                _("Failed importing backup {0}!").format(backup_name),
                "dialog-error-symbolic")
        return False

    def import_backup_bottle(self, scope:str, path:str) -> None:
        RunAsync(self.async_import_backup_bottle, None, [scope, path])
