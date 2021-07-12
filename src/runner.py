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
import json
import tarfile
import time
import shutil
import re
import urllib.request
import fnmatch
import requests

from typing import Union, NewType

from gi.repository import Gtk, GLib

from glob import glob
from pathlib import Path
from datetime import datetime

from .download import DownloadManager
from .utils import UtilsTerminal, UtilsLogger, UtilsFiles, RunAsync, CabExtract, validate_url

logging = UtilsLogger()

'''Define custom types for better understanding of the code'''
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)

class BottlesRunner:

    '''Repositories URLs'''
    components_repository = "https://raw.githubusercontent.com/bottlesdevs/components/main/"
    components_repository_index = "%s/index.yml" % components_repository

    dependencies_repository = "https://raw.githubusercontent.com/bottlesdevs/dependencies/main/"
    dependencies_repository_index = "%s/index.yml" % dependencies_repository

    installers_repository = "https://raw.githubusercontent.com/bottlesdevs/programs/main/"
    installers_repository_index = "%s/index.yml" % installers_repository

    if "TESTING_REPOS" in os.environ:
        if int(os.environ["TESTING_REPOS"]) == 1:
            dependencies_repository_index = "%s/testing.yml" % dependencies_repository
            components_repository_index = "%s/testing.yml" % components_repository


    '''Icon paths'''
    icons_user = "%s/.local/share/icons" % Path.home()

    '''Local paths'''
    base_path = f"{Path.home()}/.local/share/bottles"
    if "IS_FLATPAK" in os.environ:
        base_path_n = base_path
        base_path = f"{Path.home()}/.var/app/{os.environ['FLATPAK_ID']}/data/bottles"
    temp_path = f"{base_path}/temp"
    runners_path = f"{base_path}/runners"
    bottles_path = f"{base_path}/bottles"
    dxvk_path = f"{base_path}/dxvk"
    vkd3d_path = f"{base_path}/vkd3d"


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
    vkd3d_available = []
    gamemode_available = False
    local_bottles = {}
    supported_wine_runners = {}
    supported_proton_runners = {}
    supported_dxvk = {}
    supported_vkd3d = {}
    supported_dependencies = {}
    supported_installers = {}

    '''Bottle configuration sample'''
    sample_configuration = {
        "Name": "",
        "Runner": "",
        "DXVK": "",
        "VKD3D": "",
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
            "vkd3d": False,
            "gamemode": False,
            "sync": "wine",
            "aco_compiler": False,
            "discrete_gpu": False,
            "virtual_desktop": False,
            "virtual_desktop_res": "1280x720",
            "pulseaudio_latency": False,
            "fixme_logs": False,
            "environment_variables": "",
        },
        "Installed_Dependencies" : [],
        "DLL_Overrides" : {},
        "Programs" : {},
        "Uninstallers": {}
    }

    '''Environments'''
    environments = {
        "gaming": {
            "Runner": "wine",
            "Parameters": {
                "dxvk": True,
                "vkd3d": True,
                "sync": "esync",
                "discrete_gpu": True,
                "pulseaudio_latency": True
            }
        },
        "software": {
            "Runner": "wine",
            "Parameters": {
                "dxvk": True,
                "vkd3d": True
            }
        }
    }

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.settings = window.settings
        self.utils_conn = window.utils_conn

        self.check_gamemode()
        self.fetch_components()
        self.fetch_dependencies()
        self.fetch_installers()
        self.check_runners(install_latest=False)
        self.check_dxvk(install_latest=True)
        self.check_vkd3d(install_latest=True)
        self.check_bottles()
        self.clear_temp()

    '''Performs all checks in one async shot'''
    def async_checks(self, args=False, no_install=False):
        after, no_install = args
        self.check_runners_dir()
        self.check_dxvk()
        self.check_vkd3d()
        self.check_gamemode()
        self.check_runners(install_latest=not no_install, after=after)
        self.check_bottles()
        self.fetch_dependencies()
        self.fetch_installers()

    def checks(self, after=False, no_install=False):
        RunAsync(self.async_checks, None, [after, no_install])

    '''Clear temp path'''
    def clear_temp(self, force:bool=False) -> None:
        if self.settings.get_boolean("temp") or force:
            try:
                for f in os.listdir(self.temp_path):
                    os.remove(os.path.join(self.temp_path, f))
                logging.info("Temp path cleaned successfully!")
            except FileNotFoundError:
                logging.error("Failed to clear temp path!")
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
            logging.info("Runners path doens't exist, creating now.")
            os.makedirs(self.runners_path, exist_ok=True)

        if not os.path.isdir(self.bottles_path):
            logging.info("Bottles path doens't exist, creating now.")
            os.makedirs(self.bottles_path, exist_ok=True)

        if not os.path.isdir(self.dxvk_path):
            logging.info("Dxvk path doens't exist, creating now.")
            os.makedirs(self.dxvk_path, exist_ok=True)

        if not os.path.isdir(self.vkd3d_path):
            logging.info("Vkd3d path doens't exist, creating now.")
            os.makedirs(self.vkd3d_path, exist_ok=True)

        if not os.path.isdir(self.temp_path):
            logging.info("Temp path doens't exist, creating now.")
            os.makedirs(self.temp_path, exist_ok=True)

    '''Extract a component archive'''
    def extract_component(self, component:str, archive:str) -> True:
        if component in ["runner", "runner:proton"]: path = self.runners_path
        if component == "dxvk": path = self.dxvk_path
        if component == "vkd3d": path = self.vkd3d_path

        try:
            tar = tarfile.open("%s/%s" % (self.temp_path, archive))
            root_dir = tar.getnames()[0]
            tar.extractall(path)
        except EOFError:
            os.remove(os.path.join(self.temp_path, archive))
            shutil.rmtree(os.path.join(path, archive[:-7]))
            logging.error("Extraction failed! Archive ends earlier than expected.")
            return False

        if root_dir.endswith("x86_64"):
            shutil.move("%s/%s" % (path, root_dir),
                        "%s/%s" % (path, root_dir[:-7]))
        return True

    '''Download a specific component release'''
    def download_component(self, component:str, download_url:str, file:str, rename:bool=False, checksum:bool=False, func=False) -> bool:
        self.download_manager = DownloadManager(self.window)

        '''Check for missing paths'''
        self.check_runners_dir()

        '''Check if it exists in temp path then don't download'''
        file = rename if rename else file

        '''Add entry to download manager'''
        download_entry = self.download_manager.new_download(file, False)

        '''TODO: In Trento we should check if the resource exists in temp'''
        if download_url.startswith("temp/"):
            return True

        if func:
            update_func = func
        else:
            update_func = download_entry.update_status

        if os.path.isfile(f"{self.temp_path}/{file}"):
            logging.warning(f"File [{file}] already exists in temp, skipping.")
            update_func(completed=True)
        else:
            if component != "runner": # skip check for big files like runners
                download_url = requests.get(download_url, allow_redirects=True).url
            request = urllib.request.Request(download_url, method='HEAD')
            request = urllib.request.urlopen(download_url)
            if request.status == 200:
                download_size = request.headers['Content-Length']
                urllib.request.urlretrieve(
                    download_url,
                    f"{self.temp_path}/{file}",
                    reporthook=update_func)
            else:
                download_entry.remove()
                return False

        '''Rename the file if required'''
        if rename and file != rename:
            logging.info(f"Renaming [{file}] to [{rename}].")
            file_path = "%s/%s" % (self.temp_path, rename)
            os.rename("%s/%s" % (self.temp_path, file), file_path)
        else:
            file_path = "%s/%s" % (self.temp_path, file)

        '''Checksums comparison'''
        if checksum:
            checksum = checksum.lower()
            local_checksum = UtilsFiles().get_checksum(file_path)

            if local_checksum != checksum:
                logging.error(f"Downloaded file [{file}] looks corrupted.")
                logging.error(f"Source checksum: [{checksum}] downloaded: [{local_checksum}]")
                self.window.send_notification(
                    "Bottles",
                    _("Downloaded file {0} looks corrupted. Try again.").format(
                        file),
                    "dialog-error-symbolic",
                    user_settings=False)

                os.remove(file_path)
                download_entry.remove()
                return False

        download_entry.remove()
        return True

    '''Component installation'''
    def async_install_component(self, args:list) -> None:
        component_type, component_name, after, func, checks = args

        manifest = self.fetch_component_manifest(component_type, component_name)

        '''Notify if the user allows it'''
        self.window.send_notification(
            _("Download manager"),
            _("Installing {0} runner …").format(component_name),
            "document-save-symbolic")

        logging.info(f"Installing component: [{component_name}].")

        '''Download component'''
        download = self.download_component(component_type,
                                manifest["File"][0]["url"],
                                manifest["File"][0]["file_name"],
                                manifest["File"][0]["rename"],
                                checksum=manifest["File"][0]["file_checksum"],
                                func=func)

        if not download and func:
            return func(failed=True)

        '''Extract component archive'''
        if manifest["File"][0]["rename"]:
            archive = manifest["File"][0]["rename"]
        else:
            archive = manifest["File"][0]["file_name"]


        self.extract_component(component_type, archive)

        '''Empty the component lists and repopulate'''
        if component_type in ["runner", "runner:proton"]:
            self.runners_available = []
            self.check_runners()

        if component_type == "dxvk":
            self.dxvk_available = []
            self.check_dxvk()

        if component_type == "vkd3d":
            self.vkd3d_available = []
            self.check_vkd3d()

        '''Notify if the user allows it'''
        self.window.send_notification(
            _("Download manager"),
            _("Component {0} successfully installed!").format(component_name),
            "software-installed-symbolic")

        '''Execute a method at the end if passed'''
        if after:
            after()

        '''Re-populate local lists'''
        self.fetch_components()

    def install_component(self, component_type:str, component_name:str, after=False, func=False, checks=True) -> None:
        if self.utils_conn.check_connection(True):
            RunAsync(self.async_install_component, None, [component_type, component_name, after, func, checks])

    '''
    Method for deoendency installations
    '''
    def async_install_dependency(self, args:list) -> bool:
        configuration, dependency, widget = args
        self.download_manager = DownloadManager(self.window)

        if configuration["Versioning"]:
            self.async_create_bottle_state([
                configuration,
                f"before {dependency[0]}",
                True, False, None
            ])

        '''Notify if the user allows it'''
        self.window.send_notification(
            _("Download manager"),
             _("Installing {0} dependency in bottle {1} …").format(
                 dependency[0], configuration.get("Name")),
             "document-save-symbolic")

        '''Add entry to download manager'''
        download_entry = self.download_manager.new_download(dependency[0], False)

        logging.info(
            f"Installing dependency: [{dependency[0]}] in bottle: [{configuration['Name']}].")

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
                            f"Removing [{dll}] from system32 in bottle: [{configuration['Name']}]")
                        os.remove("%s/%s/drive_c/windows/system32/%s" % (
                            self.bottles_path, configuration.get("Name"), dll))
                    except FileNotFoundError:
                        logging.error(
                            f"[{dll}] not found in bottle: [{configuration['Name']}], failed removing from system32.")

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
                    self.run_executable(
                        configuration=configuration,
                        file_path=f"{self.temp_path}/{file}",
                        arguments=step.get("arguments"),
                        environment=step.get("environment"))
                else:
                    widget.btn_install.set_sensitive(True)
                    return False

            '''Step type: cab_extract'''
            if step["action"] == "cab_extract":
                if validate_url(step["url"]):
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

                        CabExtract(f"{self.temp_path}/{file}", dependency[0])

                elif step["url"].startswith("temp/"):
                    path = step["url"]
                    path = path.replace("temp/", f"{self.temp_path}/")
                    CabExtract(f"{path}/{step.get('file_name')}", dependency[0])

            '''Step type: copy_cab_dll'''
            if step["action"] == "copy_cab_dll":
                path = step["url"]
                path = path.replace("temp/", f"{self.temp_path}/")
                bottle_path = self.get_bottle_path(configuration)

                shutil.copyfile(
                    f"{path}/{step.get('file_name')}",
                    f"{bottle_path}/drive_c/{step.get('dest')}")

            '''Step type: override_dll'''
            if step["action"] == "override_dll":
                self.reg_add(
                    configuration,
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=step.get("dll"),
                    data=step.get("type"))

        '''Add dependency to bottle configuration'''
        if dependency[0] not in configuration.get("Installed_Dependencies"):
            dependencies = [dependency[0]]
            if configuration.get("Installed_Dependencies"):
                dependencies = configuration["Installed_Dependencies"]+[dependency[0]]

            self.update_configuration(
                configuration,
                "Installed_Dependencies",
                dependencies)

            if dependency_manifest.get("Uninstaller"):
                self.update_configuration(
                    configuration,
                    dependency[0],
                    dependency_manifest["Uninstaller"],
                    "Uninstallers")

        '''Remove entry from download manager'''
        download_entry.remove()

        '''Hide installation button and show remove button'''
        GLib.idle_add(widget.btn_install.set_visible, False)
        GLib.idle_add(widget.btn_remove.set_visible, True)
        GLib.idle_add(widget.btn_remove.set_sensitive, True)

        return True

    def install_dependency(self, configuration:BottleConfig, dependency:list, widget:Gtk.Widget) -> None:
        if self.utils_conn.check_connection(True):
            RunAsync(self.async_install_dependency, None, [configuration,
                                                           dependency,
                                                           widget])

    def remove_dependency(self, configuration:BottleConfig, dependency:list, widget:Gtk.Widget) -> None:
        logging.info(
            f"Removing dependency: [{ dependency[0]}] from bottle: [{configuration['Name']}] configuration.")

        uuid = False

        '''Run uninstaller'''
        if dependency[0] in configuration["Uninstallers"]:
            uninstaller = configuration["Uninstallers"][dependency[0]]
            command = f"uninstaller --list | grep '{uninstaller}' | cut -f1 -d\|"
            uuid = self.run_command(
                configuration=configuration,
                command=command,
                terminal=False,
                environment=False,
                comunicate=True)
            uuid = uuid.strip()

        self.run_uninstaller(configuration, uuid)

        '''Remove dependency from bottle configuration'''
        configuration["Installed_Dependencies"].remove(dependency[0])
        self.update_configuration(configuration,
                                  "Installed_Dependencies",
                                  configuration["Installed_Dependencies"])

        '''Show installation button and hide remove button'''
        GLib.idle_add(widget.btn_install.set_visible, True)
        GLib.idle_add(widget.btn_remove.set_visible, False)

    def remove_program(self, configuration:BottleConfig, program_name: str):
        logging.info(
            f"Removing program: [{ program_name }] from bottle: [{configuration['Name']}] configuration.")

        uuid = False

        '''Run uninstaller'''
        command = f"uninstaller --list | grep '{program_name}' | cut -f1 -d\|"
        uuid = self.run_command(
            configuration=configuration,
            command=command,
            terminal=False,
            environment=False,
            comunicate=True)
        uuid = uuid.strip()

        self.run_uninstaller(configuration, uuid)


    '''Run installer'''
    def run_installer(self, configuration:BottleConfig, installer:list, widget:Gtk.Widget) -> None:
        '''TODO: scheduled for Trento'''
        print(installer)

    '''Check local runners'''
    def check_runners(self, install_latest:bool=True, after=False) -> bool:
        runners = glob("%s/*/" % self.runners_path)
        self.runners_available = []

        '''Check system wine'''
        if shutil.which("wine") is not None:
            version = subprocess.Popen(
                "wine --version",
                stdout=subprocess.PIPE,
                shell=True).communicate()[0].decode("utf-8")
            version = f'sys-{version.split(" ")[0]}'
            self.runners_available.append(version)

        '''Check Bottles runners'''

        for runner in runners:
            self.runners_available.append(runner.split("/")[-2])

        if len(self.runners_available) > 0:
            logging.info(f"Runners found: [{'|'.join(self.runners_available)}]")

        '''
        If there are no locally installed runners, download the latest
        build for vaniglia from the components repository.
        A very special thanks to Lutris & GloriousEggroll for extra builds <3!
        '''

        tmp_runners = [x for x in self.runners_available if not x.startswith('sys-')]

        if len(tmp_runners) == 0 and install_latest:
            logging.warning("No runners found.")

            '''If connected, install latest runner from repository'''
            if self.utils_conn.check_connection():
                if not self.window.settings.get_boolean("release-candidate"):
                    tmp_runners = []
                    for runner in self.supported_wine_runners.items():
                        if runner[1]["Channel"] not in ["rc", "unstable"]:
                            tmp_runners.append(runner)
                    runner_name = next(iter(tmp_runners))[0]
                else:
                    tmp_runners = self.supported_wine_runners
                    runner_name = next(iter(tmp_runners))
                self.install_component("runner", runner_name, after=after)
            else:
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
            logging.info(f"Dxvk found: [{'|'.join(self.dxvk_available)}]")

        if len(self.dxvk_available) == 0 and install_latest:
            logging.warning("No dxvk found.")

            '''If connected, install latest dxvk from repository'''
            if self.utils_conn.check_connection():
                try:
                    dxvk_version = next(iter(self.supported_dxvk))
                    self.install_component("dxvk", dxvk_version, checks=False)
                except StopIteration:
                    return False
            else:
                return False
        return True

    '''Check local vkd3d'''
    def check_vkd3d(self, install_latest:bool=True) -> bool:
        vkd3d_list = glob("%s/*/" % self.vkd3d_path)
        self.vkd3d_available = []

        for vkd3d in vkd3d_list: self.vkd3d_available.append(vkd3d.split("/")[-2])

        if len(self.vkd3d_available) > 0:
            logging.info(f"Vkd3d found: [{'|'.join(self.vkd3d_available)}]")

        if len(self.vkd3d_available) == 0 and install_latest:
            logging.warning("No vkd3d found.")

            '''If connected, install latest vkd3d from repository'''
            if self.utils_conn.check_connection():
                try:
                    vkd3d_version = next(iter(self.supported_vkd3d))
                    self.install_component("vkd3d", vkd3d_version, checks=False)
                except StopIteration:
                    return False
            else:
                return False
        return True

    '''Check for gamemode in the system'''
    def check_gamemode(self):
        if shutil.which("gamemoderun") is not None:
            status = subprocess.call([
                "systemctl", "is-active", "--quiet", "gamemoded"])
            if status == 3:
                status = subprocess.call([
                    "systemctl", "--user", "is-active", "--quiet", "gamemoded"])
            if status == 0:
                self.gamemode_available = True

    def find_program_icon(self, program_name):
        logging.debug(f"Searching [{program_name}] icon..")
        pattern = "*%s*" % program_name
        for root, dirs, files in os.walk(self.icons_user):
            for name in files:
                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    name = name.split("/")[-1][:-4]
                    return name
        return "application-x-executable"

    '''Get installed programs'''
    def get_programs(self, configuration:BottleConfig) -> list:
        '''TODO: Programs found should be stored in a database
        TN: Will be fixed in Trento release'''
        bottle = "%s/%s" % (self.bottles_path, configuration.get("Path"))
        results =  glob("%s/drive_c/users/*/Start Menu/Programs/**/*.lnk" % bottle,
                        recursive=True)
        results += glob("%s/drive_c/ProgramData/Microsoft/Windows/Start Menu/Programs/**/*.lnk" % bottle,
                        recursive=True)
        results += glob("%s/drive_c/users/*/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/**/*.lnk" % bottle,
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

                        executable_path = re.search('C:(.*).exe', lnk)
                        if executable_path is not None:
                            executable_path = executable_path.group(0)
                        else:
                            executable_path = re.search('C:(.*).bat', lnk).group(0)

                        if executable_path.find("ninstall") < 0:
                            path = path.replace(".lnk", "")
                            executable_name = executable_path.split("\\")[-1][:-4]
                            icon = self.find_program_icon(executable_name)
                            installed_programs.append([path, executable_path, icon])
                except:
                    logging.error(F"Cannot find executable for [{path}].")

        return installed_programs


    '''Fetch installers'''
    def fetch_installers(self) -> bool:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen(self.installers_repository_index) as url:
                index = yaml.safe_load(url.read())

                for installer in index.items():
                    self.supported_installers[installer[0]] = installer[1]
        else:
            return False
        return True

    '''Fetch installer manifest'''
    def fetch_installer_manifest(self, installer_name:str, installer_category:str, plain:bool=False) -> Union[str, dict, bool]:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen("%s/%s/%s.yml" % (
                self.installers_repository,
                installer_category,
                installer_name
            )) as url:
                if plain:
                    return url.read().decode("utf-8")
                return yaml.safe_load(url.read())

            return False

    '''Fetch components'''
    def fetch_components(self) -> bool:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen(self.components_repository_index) as url:
                index = yaml.safe_load(url.read())

                for component in index.items():
                    if component[1]["Category"] == "runners":

                        if component[1]["Sub-category"] == "wine":
                            self.supported_wine_runners[component[0]] = component[1]
                            if component[0] in self.runners_available:
                                self.supported_wine_runners[component[0]]["Installed"] = True

                        if component[1]["Sub-category"] == "proton":
                            self.supported_proton_runners[component[0]] = component[1]
                            if component[0] in self.runners_available:
                                self.supported_proton_runners[component[0]]["Installed"] = True

                    if component[1]["Category"] == "dxvk":
                        self.supported_dxvk[component[0]] = component[1]
                        if component[0] in self.dxvk_available:
                            self.supported_dxvk[component[0]]["Installed"] = True

                    if component[1]["Category"] == "vkd3d":
                        self.supported_vkd3d[component[0]] = component[1]
                        if component[0] in self.vkd3d_available:
                            self.supported_vkd3d[component[0]]["Installed"] = True
                return True
        return False

    '''Fetch component manifest'''
    def fetch_component_manifest(self, component_type:str, component_name:str, plain:bool=False) -> Union[str, dict, bool]:
        if component_type == "runner":
            component = self.supported_wine_runners[component_name]
        if component_type == "runner:proton":
            component = self.supported_proton_runners[component_name]
        if component_type == "dxvk":
            component = self.supported_dxvk[component_name]
        if component_type == "vkd3d":
            component = self.supported_vkd3d[component_name]

        if self.utils_conn.check_connection():
            if "Sub-category" in component:
                manifest_url = "%s/%s/%s/%s.yml" % (
                    self.components_repository,
                    component["Category"],
                    component["Sub-category"],
                    component_name)
            else:
                manifest_url = "%s/%s/%s.yml" % (
                    self.components_repository,
                    component["Category"],
                    component_name)
            with urllib.request.urlopen(manifest_url) as url:
                if plain:
                    return url.read().decode("utf-8")
                return yaml.safe_load(url.read())

            return False

    '''Fetch dependencies'''
    def fetch_dependencies(self) -> bool:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen(self.dependencies_repository_index) as url:
                index = yaml.safe_load(url.read())

                for dependency in index.items():
                    self.supported_dependencies[dependency[0]] = dependency[1]
        else:
            return False
        return True

    '''Fetch dependency manifest'''
    def fetch_dependency_manifest(self, dependency_name:str, dependency_category:str, plain:bool=False) -> Union[str, dict, bool]:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen("%s/%s/%s.yml" % (
                self.dependencies_repository,
                dependency_category,
                dependency_name
            )) as url:
                if plain:
                    return url.read().decode("utf-8")
                return yaml.safe_load(url.read())

            return False

    '''Check Bottles data from old directory (only Flatpak)'''
    def check_bottles_n(self):
        data = glob(f"{self.base_path_n}/*")
        print(len(data))
        return len(data)

    '''Check local bottles'''
    def check_bottles(self, silent:bool=False) -> None:
        bottles = glob("%s/*/" % self.bottles_path)

        '''
        For each bottle add the path name to the `local_bottles` variable
        and append the configuration
        '''
        for bottle in bottles:
            bottle_name_path = bottle.split("/")[-2]

            '''
            Check for old json bottle configurations and convert to
            the new yaml format
            TODO: this check will be removed in the near future
            '''
            try:
                with open(f'{bottle}/bottle.json') as c_json_file:
                    c_json = json.load(c_json_file)
                    with open(f'{bottle}/bottle.yml', "w") as c_yaml_file:
                        yaml.dump(c_json, c_yaml_file, allow_unicode=True)
                os.remove(f'{bottle}/bottle.json')
            except FileNotFoundError:
                pass

            try:
                configuration_file = open('%s/bottle.yml' % bottle)
                configuration_file_yaml = yaml.safe_load(configuration_file)
                configuration_file.close()

                missing_keys = self.sample_configuration.keys() - configuration_file_yaml.keys()
                for key in missing_keys:
                    logging.warning(
                        f"Key: [{key}] not in bottle: [{bottle.split('/')[-2]}] configuration, updating.")
                    self.update_configuration(configuration_file_yaml,
                                              key,
                                              self.sample_configuration[key])

                missing_parameters_keys = self.sample_configuration["Parameters"].keys() - configuration_file_yaml["Parameters"].keys()
                for key in missing_parameters_keys:
                    logging.warning(
                        f"Key: [{key}] not in bottle: [{bottle.split('/')[-2]}] configuration Parameters, updating.")
                    self.update_configuration(configuration_file_yaml,
                                              key,
                                              self.sample_configuration["Parameters"][key],
                                              scope="Parameters")
                self.local_bottles[bottle_name_path] = configuration_file_yaml

            except FileNotFoundError:
                new_configuration_yaml = self.sample_configuration.copy()
                new_configuration_yaml["Broken"] = True
                new_configuration_yaml["Name"] = bottle_name_path
                new_configuration_yaml["Environment"] = "Undefined"
                self.local_bottles[bottle_name_path] = new_configuration_yaml


        if len(self.local_bottles) > 0 and not silent:
            logging.info(f"Bottles found: {'|'.join(self.local_bottles)}")

    '''Get bottle path by configuration'''
    def get_bottle_path(self, configuration:BottleConfig) -> str:
        if configuration.get("Custom_Path"):
            return configuration.get("Path")
        return "%s/%s" % (self.bottles_path, configuration.get("Path"))

    '''Update parameters in bottle configuration'''
    def update_configuration(self, configuration:BottleConfig, key:str, value:str, scope:str="", no_update:bool=False, remove:bool=False) -> dict:
        logging.info(
            f"Setting Key: [{key}] to [{value}] for bottle: [{configuration['Name']}] …")

        bottle_complete_path = self.get_bottle_path(configuration)

        if scope != "":
            configuration[scope][key] = value
            if remove:
                del configuration[scope][key]
        else:
            configuration[key] = value
            if remove:
                del configuration[key]

        with open("%s/bottle.yml" % bottle_complete_path,
                  "w") as configuration_file:
            yaml.dump(configuration, configuration_file, indent=4)
            configuration_file.close()

        if not no_update:
            self.update_bottles(silent=True)

        '''Update Update_Date in configuration'''
        configuration["Update_Date"] = str(datetime.now())
        return configuration

    '''Create new wineprefix'''
    def async_create_bottle(self, args:list) -> None:
        logging.info("Creating the wineprefix …")

        name, environment, path, runner, dxvk, vkd3d, versioning, dialog = args

        update_output = dialog.update_output

        '''If there are no local runners, dxvks, vkd3ds, install them'''
        if 0 in [
            len(self.runners_available),
            len(self.dxvk_available),
            len(self.vkd3d_available)]:
            update_output(_("One or more components not found, installing latest version …"))
            self.window.page_preferences.set_dummy_runner()
            self.window.show_runners_preferences_view()
            return self.async_checks()

        if not runner: runner = self.runners_available[0]
        runner_name = runner

        if not dxvk: dxvk = self.dxvk_available[0]
        dxvk_name = dxvk

        if not vkd3d: vkd3d = self.vkd3d_available[0]
        vkd3d_name = vkd3d

        '''If runner is proton, files are located to the dist path'''
        if runner.startswith("Proton"):
            if os.path.exists("%s/%s/dist" % (self.runners_path, runner)):
                runner = "%s/dist" % runner
            else:
                runner = "%s/files" % runner

        '''If runner is system'''
        if runner.startswith("sys-"):
            runner = "wine"
        else:
            runner = "%s/%s/bin/wine64" % (self.runners_path, runner)

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
        RunAsync(dialog.pulse, None)

        '''Execute wineboot'''
        update_output( _("The wine configuration is being updated …"))
        command = "DISPLAY=:3.0 WINEDEBUG=fixme-all WINEPREFIX={path} WINEARCH=win64 {runner} wineboot /nogui".format(
            path = bottle_complete_path,
            runner = runner
        )
        subprocess.Popen(command, shell=True).communicate()
        update_output(_("Wine configuration updated!"))
        time.sleep(1)

        '''Generate bottle configuration file'''
        logging.info("Generating Bottle configuration file …")
        update_output("Generating Bottle configuration file …")

        configuration = self.sample_configuration
        configuration["Name"] = bottle_name
        configuration["Runner"] = runner_name
        configuration["DXVK"] = dxvk_name
        configuration["VKD3D"] = vkd3d_name
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
        logging.info(f"Applying environment: [{environment}] …")
        update_output(_("Applying environment: {0} …").format(environment))
        if environment != "Custom":
            environment_parameters = self.environments[environment.lower()]["Parameters"]
            for parameter in configuration["Parameters"]:
                if parameter in environment_parameters:
                    configuration["Parameters"][parameter] = environment_parameters[parameter]

        time.sleep(1)

        '''Save bottle configuration'''
        with open(f"{bottle_complete_path}/bottle.yml", "w") as configuration_file:
            yaml.dump(configuration, configuration_file, indent=4)
            configuration_file.close()

        time.sleep(5)

        '''Perform dxvk installation if configured'''
        if configuration["Parameters"]["dxvk"]:
            logging.info("Installing dxvk …")
            update_output( _("Installing dxvk …"))
            self.install_dxvk(configuration, version=dxvk_name)

        '''Perform vkd3d installation if configured'''
        if configuration["Parameters"]["vkd3d"]:
            logging.info("Installing vkd3d …")
            update_output( _("Installing vkd3d …"))
            self.install_vkd3d(configuration, version=vkd3d_name)

        time.sleep(1)

        '''Create first state if versioning enabled'''
        if versioning:
            logging.info("Creating versioning state 0 …")
            update_output( _("Creating versioning state 0 …"))
            self.async_create_bottle_state([configuration, "First boot", False, True, False])

        '''Set status created and UI usability'''
        logging.info(f"Bottle: [{bottle_name}] successfully created!")
        update_output(
            _("Your new bottle: {0} is now ready!").format(bottle_name))

        time.sleep(2)

        dialog.finish()

    def create_bottle(self, name, environment:str, path:str=False, runner:RunnerName=False, dxvk:bool=False, vkd3d:bool=False, versioning:bool=False, dialog:Gtk.Widget=None) -> None:
        RunAsync(self.async_create_bottle, None, [name,
                                                  environment,
                                                  path,
                                                  runner,
                                                  dxvk,
                                                  vkd3d,
                                                  versioning,
                                                  dialog])

    '''Get latest installed runner'''
    def get_latest_runner(self, runner_type:RunnerType="wine") -> list:
        try:
            if runner_type in ["", "wine"]:
                return [idx for idx in self.runners_available if idx.lower().startswith("lutris")][0]
            return [idx for idx in self.runners_available if idx.lower().startswith("proton")][0]
        except IndexError:
            return "Undefined"

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
        logging.info("Deleting a bottle …")

        configuration = args[0]

        '''Delete path with all files'''
        path = configuration.get("Path")

        if path != "":
            if not configuration.get("Custom_Path"):
                path = "%s/%s" % (self.bottles_path, path)

            shutil.rmtree(path)
            del self.local_bottles[configuration.get("Path")]

            self.window.page_list.update_bottles()

            logging.info(f"Successfully deleted bottle in path: [{path}]")
            return True

        logging.error("Empty path found, failing to avoid disasters.")
        return False

    def delete_bottle(self, configuration:BottleConfig) -> None:
        RunAsync(self.async_delete_bottle, None, [configuration])

    ''' Repair a bottle generating a new configuration'''
    def repair_bottle(self, configuration:BottleConfig) -> bool:
        logging.info(f"Trying to repair the bottle: [{configuration['Name']}] …")

        bottle_complete_path = f"{self.bottles_path}/{configuration['Name']}"

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
            with open("%s/bottle.yml" % bottle_complete_path,
                      "w") as configuration_file:
                yaml.dump(new_configuration, configuration_file, indent=4)
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
            f"Adding Key: [{key}] with Value: [{value}] and Data: [{data}] in register bottle: {configuration['Name']}")

        self.run_command(configuration, "reg add '%s' /v %s /d %s /f" % (
            key, value, data))

    '''Remove key from register'''
    def reg_delete(self, configuration:BottleConfig, key:str, value:str) -> None:
        logging.info(
            f"Removing Value: [{key}] for Key: [{value}] in register bottle: {configuration['Name']}")

        self.run_command(configuration, "reg delete '%s' /v %s /f" % (
            key, value))

    '''
    Install dxvk using official script
    TODO: A good task for the future is to use the built-in methods
    to install the new dlls and register the override for dxvk.
    '''
    def install_dxvk(self, configuration:BottleConfig, remove:bool=False, version:str=False) -> bool:
        logging.info(f"Installing dxvk for bottle: [{configuration['Name']}].")

        if version:
            dxvk_version = version
        else:
            dxvk_version = configuration.get("DXVK")

        option = "uninstall" if remove else "install"

        command = 'DISPLAY=:3.0 WINEPREFIX="{path}" PATH="{runner}:$PATH" {dxvk_setup} {option} --with-d3d10'.format (
            path = "%s/%s" % (self.bottles_path, configuration.get("Path")),
            runner = "%s/%s/bin" % (self.runners_path, configuration.get("Runner")),
            dxvk_setup = "%s/%s/setup_dxvk.sh" % (self.dxvk_path, dxvk_version),
            option = option)

        return subprocess.Popen(command, shell=True).communicate()

    '''
    Install vkd3d using official script
    '''
    def install_vkd3d(self, configuration:BottleConfig, remove:bool=False, version:str=False) -> bool:
        logging.info(f"Installing vkd3d for bottle: [{configuration['Name']}].")

        if version:
            vkd3d_version = version
        else:
            vkd3d_version = configuration.get("VKD3D")

        if not vkd3d_version:
            vkd3d_version = self.vkd3d_available[0]
            self.update_configuration(configuration, "VKD3D", vkd3d_version)

        option = "uninstall" if remove else "install"

        command = 'DISPLAY=:3.0 WINEPREFIX="{path}" PATH="{runner}:$PATH" {vkd3d_setup} {option}'.format (
            path = "%s/%s" % (self.bottles_path, configuration.get("Path")),
            runner = "%s/%s/bin" % (self.runners_path, configuration.get("Runner")),
            vkd3d_setup = "%s/%s/setup_vkd3d_proton.sh" % (self.vkd3d_path, vkd3d_version),
            option = option)

        return subprocess.Popen(command, shell=True).communicate()

    '''Remove dxvk using official script'''
    def remove_dxvk(self, configuration:BottleConfig) -> None:
        logging.info(f"Removing dxvk for bottle: [{configuration['Name']}].")

        self.install_dxvk(configuration, remove=True)

    '''Remove vkd3d using official script'''
    def remove_vkd3d(self, configuration:BottleConfig) -> None:
        logging.info(f"Removing vkd3d for bottle: [{configuration['Name']}].")

        self.install_vkd3d(configuration, remove=True)

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
    def run_executable(self, configuration:BottleConfig, file_path:str, arguments:str=False, environment:dict=False) -> None:
        logging.info("Running an executable on the wineprefix …")

        if "msi" in file_path.split("."):
            command = "msiexec /i '%s'" % file_path
        elif "bat" in file_path.split("."):
            command = "wineconsole cmd /c '%s'" % file_path
        else:
            command = "'%s'" % file_path

        if arguments: command = "%s %s" % (command, arguments)

        RunAsync(self.run_command, None, configuration, command, False, environment)

    def run_wineboot(self, configuration:BottleConfig) -> None:
        logging.info("Running wineboot on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "wineboot -u")

    def run_winecfg(self, configuration:BottleConfig) -> None:
        logging.info("Running winecfg on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "winecfg")

    def run_winetricks(self, configuration:BottleConfig) -> None:
        logging.info("Running winetricks on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "winetricks")

    def run_debug(self, configuration:BottleConfig) -> None:
        logging.info("Running a debug console on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "winedbg", True)

    def run_cmd(self, configuration:BottleConfig) -> None:
        logging.info("Running a CMD on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "cmd", True)

    def run_taskmanager(self, configuration:BottleConfig) -> None:
        logging.info("Running a Task Manager on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "taskmgr")

    def run_controlpanel(self, configuration:BottleConfig) -> None:
        logging.info("Running a Control Panel on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "control")

    def run_uninstaller(self, configuration:BottleConfig, uuid:str=False) -> None:
        logging.info("Running an Uninstaller on the wineprefix …")
        command = "uninstaller"
        if uuid:
            command = f"uninstaller --remove '{uuid}'"
        RunAsync(self.run_command, None, configuration, command)

    def run_regedit(self, configuration:BottleConfig) -> None:
        logging.info("Running a Regedit on the wineprefix …")
        RunAsync(self.run_command, None, configuration, "regedit")

    '''Execute command in a bottle'''
    def run_command(self, configuration:BottleConfig, command:str, terminal:bool=False, environment:dict=False, comunicate:bool=False) -> bool:
        if "IS_FLATPAK" in os.environ or "SNAP" in os.environ and terminal:
            terminal = False
            if command in ["winedbg", "cmd"]:
                command = f"wineconsole {command}"

        path = configuration.get("Path")
        runner = configuration.get("Runner")

        '''If runner is proton then set path to /dist'''
        if runner.startswith("Proton"):
            if os.path.exists("%s/%s/dist" % (self.runners_path, runner)):
                runner = "%s/dist" % runner
            else:
                runner = "%s/files" % runner

        '''If runner is system'''
        if runner.startswith("sys-"):
            runner = "wine"
        else:
            runner = "%s/%s/bin/wine64" % (self.runners_path, runner)

        if not configuration.get("Custom_Path"):
            path = "%s/%s" % (self.bottles_path, path)

        '''Check for executable args from bottle configuration'''
        environment_vars = []
        dll_overrides = []
        parameters = configuration["Parameters"]

        if configuration.get("DLL_Overrides"):
            for dll in configuration.get("DLL_Overrides").items():
                dll_overrides.append("%s=%s" % (dll[0], dll[1]))

        if parameters["environment_variables"]:
            environment_vars.append(parameters["environment_variables"])

        if environment:
            if environment.get("WINEDLLOVERRIDES"):
                dll_overrides.append(environment["WINEDLLOVERRIDES"])
                del environment["WINEDLLOVERRIDES"]
            for e in environment:
                environment_vars.append(e)

        if parameters["dxvk"]:
            # dll_overrides.append("d3d11,dxgi=n")
            environment_vars.append("WINE_LARGE_ADDRESS_AWARE=1")
            environment_vars.append("DXVK_STATE_CACHE_PATH='%s'" % path)
            environment_vars.append("STAGING_SHARED_MEMORY=1")
            environment_vars.append("__GL_DXVK_OPTIMIZATIONS=1")
            environment_vars.append("__GL_SHADER_DISK_CACHE=1")
            environment_vars.append("__GL_SHADER_DISK_CACHE_PATH='%s'" % path)

        if parameters["dxvk_hud"]:
            environment_vars.append("DXVK_HUD='devinfo,memory,drawcalls,fps,version,api,compiler'")
        else:
            environment_vars.append("DXVK_HUD='compiler'")

        if parameters["sync"] == "esync":
            environment_vars.append("WINEESYNC=1") # WINEDEBUG=+esync

        if parameters["sync"] == "fsync":
            environment_vars.append("WINEFSYNC=1")

        if parameters["fixme_logs"]:
            environment_vars.append("WINEDEBUG=+fixme-all")
        else:
            environment_vars.append("WINEDEBUG=fixme-all")

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

        environment_vars.append("WINEDLLOVERRIDES='%s'" % ";".join(dll_overrides))
        environment_vars = " ".join(environment_vars)

        command = "WINEPREFIX={path} WINEARCH=win64 {env} {runner} {command}".format(
            path = path,
            env = environment_vars,
            runner = runner,
            command = command
        )

        # Check for gamemode enabled
        if self.gamemode_available and configuration["Parameters"]["gamemode"]:
            command = f"gamemoderun {command}"

        print(command)
        if terminal:
            return UtilsTerminal(command)

        if comunicate:
            return subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                shell=True).communicate()[0].decode("utf-8")

        return subprocess.Popen(command, shell=True).communicate()

    '''Send status to a bottle'''
    def send_status(self, configuration:BottleConfig, status:str) -> None:
        logging.info(f"Sending Status: [{status}] to the wineprefix …")

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
    def open_filemanager(self, configuration:BottleConfig=dict, path_type:str="bottle", runner:str="", dxvk:str="", vkd3d:str="", custom_path:str="") -> bool:
        logging.info("Opening the file manager in the path …")

        if path_type == "bottle":
            path = "%s/%s/drive_c" % (self.bottles_path,
                                      configuration.get("Path"))

        if path_type == "runner" and runner != "":
            path = "%s/%s" % (self.runners_path, runner)

        if path_type == "dxvk" and dxvk != "":
            path = "%s/%s" % (self.dxvk_path, dxvk)

        if path_type == "vkd3d" and vkd3d != "":
            path = "%s/%s" % (self.vkd3d_path, vkd3d)

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
        lutris_results = glob(f"{self.lutris_path}/*/")
        playonlinux_results = glob(f"{self.playonlinux_path}/*/")
        bottlesv1_results = glob(f"{self.bottlesv1_path}/*/")

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

        logging.info(f"Found {len(importer_wineprefixes)} wineprefixes ..")
        return importer_wineprefixes

    def import_wineprefix(self, wineprefix:dict, widget:Gtk.Widget) -> bool:
        logging.info(
            f"Importing wineprefix [{wineprefix['Name']}] in a new bottle …")

        '''Hide btn_import to prevent double imports'''
        widget.set_visible(False)

        '''Prepare bottle path for the wine prefix'''
        bottle_path = "Imported_%s" % wineprefix.get("Name")
        bottle_complete_path = "%s/%s" % (self.bottles_path, bottle_path)

        try:
            os.makedirs(bottle_complete_path, exist_ok=False)
        except:
            logging.error(
                f"Error creating bottle path for wineprefix [{wineprefix['Name']}], aborting.")
            return False

        '''Create lockfile in source path'''
        logging.info("Creating lock file in source path …")
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
        with open("%s/bottle.yml" % bottle_complete_path,
                  "w") as configuration_file:
            yaml.dump(new_configuration, configuration_file, indent=4)
            configuration_file.close()

        '''Update bottles'''
        self.update_bottles(silent=True)

        '''Notify if the user allows it'''
        self.window.send_notification(
            _("Importer"),
            _("Wineprefix {0} successfully imported!").format(
                wineprefix["Name"]), "software-installed-symbolic")


        logging.info(
            f"Wineprefix: [{wineprefix['Name']}] successfully imported!")
        return True


    def browse_wineprefix(self, wineprefix:dict) -> bool:
        return self.open_filemanager(path_type="custom",
                                     custom_path=wineprefix.get("Path"))

    '''Create new bottle state'''
    def async_create_bottle_state(self, args:list) -> bool:
        configuration, comment, update, no_update, after = args

        logging.info(
            f"Creating new state for bottle: [{configuration['Name']}] …")

        self.download_manager = DownloadManager(self.window)

        bottle_path = self.get_bottle_path(configuration)
        first = False if os.path.isdir('%s/states/' % bottle_path) else True

        '''Set UI to not usable'''
        self.window.set_usable_ui(False)

        '''List all bottle files'''
        current_index = self.get_bottle_index(configuration)

        download_entry = self.download_manager.new_download(
            _("Generating state files index …"), False)

        '''If it is not the first state, compare files with the previous one'''
        if not first:
            states_file = open('%s/states/states.yml' % bottle_path)
            states_file_yaml = yaml.safe_load(states_file)
            states_file.close()

            state_index_file = open('%s/states/%s/index.yml' % (
                bottle_path, str(configuration.get("State"))))
            state_index = yaml.safe_load(state_index_file)
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

            state_id = str(len(states_file_yaml.get("States")))
        else:
            new_state_index = {
                "Update_Date": str(datetime.now()),
                "Additions": current_index["Files"],
                "Removed": [],
                "Changes": []
            }
            state_id = "0"

        state_path = "%s/states/%s" % (bottle_path, state_id)

        download_entry.destroy()
        download_entry = self.download_manager.new_download(
            _("Creating a restore point …"), False)

        try:
            '''Make state structured path'''
            os.makedirs("%s/states/%s/drive_c" % (bottle_path, state_id), exist_ok=True)

            '''Save index.yml with state edits'''
            with open("%s/index.yml" % (state_path),
                      "w") as state_index_file:
                yaml.dump(new_state_index, state_index_file, indent=4)
                state_index_file.close()

            '''Save files.yml with bottle files'''
            with open("%s/files.yml" % (state_path),
                      "w") as state_files_file:
                yaml.dump(current_index, state_files_file, indent=4)
                state_files_file.close()
        except:
            return False

        download_entry.destroy()
        download_entry = self.download_manager.new_download(
            _("Updating index …"), False)

        '''Copy indexed files in the new state path'''
        for file in current_index["Files"]:
            os.makedirs("{0}/drive_c/{1}".format(
                state_path,
                "/".join(file["file"].split("/")[:-1])), exist_ok=True)
            source = "{0}/drive_c/{1}".format(bottle_path, file["file"])
            target = "{0}/drive_c/{1}".format(state_path, file["file"])
            shutil.copyfile(source, target)

        time.sleep(5)

        download_entry.destroy()
        download_entry = self.download_manager.new_download(
            _("Updating states …"), False)

        '''Update the states.yml file'''
        new_state = {
            "Creation_Date": str(datetime.now()),
            "Comment": comment,
			# "Files": [file["file"] for file in current_index["Files"]]
		}

        if not first:
            new_state_file = {
                "Update_Date": str(datetime.now()),
                "States": states_file_yaml.get("States")
            }
            new_state_file["States"][state_id] = new_state
        else:
            new_state_file = {
                "Update_Date": str(datetime.now()),
                "States": {"0": new_state}
            }

        try:
            with open('%s/states/states.yml' % bottle_path, "w") as states_file:
                yaml.dump(new_state_file, states_file, indent=4)
                states_file.close()
        except:
            return False

        '''Create new index.yml in the states root'''
        try:
            with open('%s/states/index.yml' % bottle_path,
                      "w") as current_index_file:
                yaml.dump(current_index, current_index_file, indent=4)
                current_index_file.close()
        except:
            return False

        '''Update State in bottle configuration'''
        self.update_configuration(configuration, "State", state_id)
        self.update_configuration(configuration, "Versioning", True)

        logging.info(f"New state [{state_id}] created successfully!")

        '''Update states'''
        if update:
            self.window.page_details.update_states()

        '''Update bottles'''
        time.sleep(2)
        self.update_bottles()

        download_entry.destroy()

        '''Execute caller function after all'''
        if after:
            after()

        '''Set UI to usable again'''
        self.window.set_usable_ui(True)

        return True

    def create_bottle_state(self, configuration:BottleConfig, comment:str="Not commented", update:bool=False, no_update:bool=False, after:bool=False) -> None:
        RunAsync(self.async_create_bottle_state, None, [configuration, comment, update, no_update, after])

    '''Get edits for a state'''
    def get_bottle_state_edits(self, configuration:BottleConfig, state_id:str, plain:bool=False) -> dict:
        bottle_path = self.get_bottle_path(configuration)

        try:
            file = open('%s/states/%s/index.yml' % (bottle_path, state_id))
            files = file.read() if plain else yaml.safe_load(file.read())
            file.close()
            return files
        except:
            return {}

    '''Get files for a state'''
    def get_bottle_state_files(self, configuration:BottleConfig, state_id:str, plain:bool=False) -> dict:
        bottle_path = self.get_bottle_path(configuration)

        try:
            file = open('%s/states/%s/files.yml' % (bottle_path, state_id))
            files = file.read() if plain else yaml.safe_load(file.read())
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

        logging.info(f"Restoring to state: [{state_id}]")

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
        logging.info(f"[{len(remove_files)}] files to remove.")
        logging.info(f"[{len(edit_files)}] files to replace.")

        '''Check for new files'''
        add_files = []
        for file in state_index.get("Files"):
            if file["file"] not in [file["file"] for file in bottle_index.get("Files")]:
                add_files.append(file)
        logging.info(f"[{len(add_files)}] files to add.")

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
            states_file = open('%s/states/states.yml' % bottle_path)
            states_file_yaml = yaml.safe_load(states_file)
            states_file.close()
            states = states_file_yaml.get("States")

            logging.info(
                f"Found [{len(states)}] states for bottle: [{configuration['Name']}]")
            return states
        except:
            logging.error(
                f"Cannot find states.yml file for bottle: [{configuration['Name']}]")

            return {}

    '''Make a bottle backup'''
    def async_backup_bottle(self, args:list) -> bool:
        configuration, scope, path = args
        self.download_manager = DownloadManager(self.window)

        '''Set UI to not usable'''
        self.window.set_usable_ui(False)

        if scope == "configuration":
            '''Backup type: configuration'''
            logging.info(
                f"Backuping configuration: [{configuration['Name']}] in [{path}]")
            try:
                with open(path, "w") as configuration_backup:
                    yaml.dump(configuration, configuration_backup, indent=4)
                    configuration_backup.close()
                backup_created = True
            except:
                backup_created = False

        else:
            '''Backup type: full'''
            logging.info(
                f"Backuping bottle: [{configuration['Name']}] in [{path}]")

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
            logging.info(f"Backup saved in path: {path}.")

            '''Notify if the user allows it'''
            self.window.send_notification(
                "Backup",
                _("Your backup for {0} is ready!").format(
                    configuration.get("Name")
                ), "software-installed-symbolic")
            return True

        logging.error(f"Failed to save backup in path: {path}.")

        '''Notify if the user allows it'''
        self.window.send_notification(
            "Backup",
            _("Failed to create backup for {0}!").format(
                configuration.get("Name")
            ), "dialog-error-symbolic")

        '''Set UI to usable again'''
        self.window.set_usable_ui(True)

        return False

    def backup_bottle(self, configuration:BottleConfig, scope:str, path:str) -> None:
        RunAsync(self.async_backup_bottle, None, [configuration, scope, path])

    def async_import_backup_bottle(self, args:list) -> bool:
        scope, path = args
        self.download_manager = DownloadManager(self.window)

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
            logging.info(f"Backup: [{path}] imported successfully.")

            '''Update bottles'''
            self.update_bottles()

            '''Notify if the user allows it'''
            self.window.send_notification(
                "Backup",
                _("Your backup {0} was imported successfully.!").format(
                    backup_name), "software-installed-symbolic")
            return True

        logging.error(f"Failed importing backup: [{backup_name}]")

        '''Notify if the user allows it'''
        self.window.send_notification(
            "Backup",
            _("Failed importing backup {0}!").format(backup_name),
            "dialog-error-symbolic")
        return False

    def import_backup_bottle(self, scope:str, path:str) -> None:
        RunAsync(self.async_import_backup_bottle, None, [scope, path])
