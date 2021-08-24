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
import patoolib
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

from ..download import DownloadManager
from ..utils import UtilsLogger, UtilsFiles, RunAsync, CabExtract, validate_url
from ..backend.runner import Runner
from ..backend.globals import Samples, BottlesRepositories, Paths, TrdyPaths
from ..backend.versioning import RunnerVersioning

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

        self.check_runners_dir()
        self.check_dxvk(install_latest=False)
        self.check_vkd3d(install_latest=False)
        self.check_runners(install_latest=False)
        self.fetch_components()
        self.fetch_dependencies()
        self.fetch_installers()
        self.check_bottles()
        self.clear_temp()

    # Performs all checks in one async shot
    def async_checks(self, args=False, no_install=False):
        after, no_install = args
        self.check_runners_dir()
        self.check_dxvk()
        self.check_vkd3d()
        self.check_runners(install_latest=not no_install, after=after)
        self.check_bottles()
        self.fetch_dependencies()
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

    # Extract a component archive
    def extract_component(self, component: str, archive: str) -> True:
        if component in ["runner", "runner:proton"]:
            path = Paths.runners
        if component == "dxvk":
            path = Paths.dxvk
        if component == "vkd3d":
            path = Paths.vkd3d

        try:
            tar = tarfile.open("%s/%s" % (Paths.temp, archive))
            root_dir = tar.getnames()[0]
            tar.extractall(path)
        except:
            if os.path.isfile(os.path.join(Paths.temp, archive)):
                os.remove(os.path.join(Paths.temp, archive))

            if os.path.isdir(os.path.join(path, archive[:-7])):
                shutil.rmtree(os.path.join(path, archive[:-7]))

            logging.error(
                "Extraction failed! Archive ends earlier than expected.")
            return False

        if root_dir.endswith("x86_64"):
            try:
                shutil.move("%s/%s" % (path, root_dir),
                            "%s/%s" % (path, root_dir[:-7]))
            except:
                logging.error("Extraction failed! Component already exists.")
                return False
        return True

    # Download a specific component release
    def download_component(self, component: str, download_url: str, file: str, rename: bool = False, checksum: bool = False, func=False) -> bool:
        self.download_manager = DownloadManager(self.window)

        # Check for missing paths
        self.check_runners_dir()

        # Add entry to download manager
        download_entry = self.download_manager.new_download(file, False)
        time.sleep(1)

        # TODO: In Trento we should check if the resource exists in temp
        # this check is only performed by dependencies
        if download_url.startswith("temp/"):
            return True

        if func:
            update_func = func
        else:
            update_func = download_entry.update_status

        existing_file = rename if rename else file
        just_downloaded = False

        if os.path.isfile(f"{Paths.temp}/{existing_file}"):
            logging.warning(
                f"File [{existing_file}] already exists in temp, skipping.")
            GLib.idle_add(update_func, False, False, False, True)
        else:
            # skip check for big files like runners
            if component not in ["runner", "runner:proton", "installer"]:
                download_url = requests.get(
                    download_url, allow_redirects=True).url
            try:
                request = urllib.request.urlopen(download_url)
            except (urllib.error.HTTPError, urllib.error.URLError):
                GLib.idle_add(download_entry.remove)
                return False

            if request.status == 200:
                try:
                    urllib.request.urlretrieve(
                        download_url,
                        f"{Paths.temp}/{file}",
                        reporthook=update_func)
                except:
                    # workaround https://github.com/bottlesdevs/Bottles/issues/426
                    GLib.idle_add(download_entry.remove)
                    return False
                just_downloaded = True
            else:
                GLib.idle_add(download_entry.remove)
                return False

        # Rename the file if required
        if rename and just_downloaded:
            logging.info(f"Renaming [{file}] to [{rename}].")
            file_path = f"{Paths.temp}/{rename}"
            os.rename(f"{Paths.temp}/{file}", file_path)
        else:
            file_path = f"{Paths.temp}/{existing_file}"

        # Checksums comparison
        if checksum:
            checksum = checksum.lower()
            local_checksum = UtilsFiles().get_checksum(file_path)

            if local_checksum != checksum:
                logging.error(f"Downloaded file [{file}] looks corrupted.")
                logging.error(
                    f"Source checksum: [{checksum}] downloaded: [{local_checksum}]")

                os.remove(file_path)
                GLib.idle_add(download_entry.remove)
                return False

        GLib.idle_add(download_entry.remove)
        return True

    # Component installation
    def async_install_component(self, args: list) -> None:
        component_type, component_name, after, func, checks = args

        manifest = self.fetch_component_manifest(
            component_type, component_name)
        
        if not manifest:
            return func(failed=True)

        logging.info(f"Installing component: [{component_name}].")

        # Download component
        download = self.download_component(component_type,
                                           manifest["File"][0]["url"],
                                           manifest["File"][0]["file_name"],
                                           manifest["File"][0]["rename"],
                                           checksum=manifest["File"][0]["file_checksum"],
                                           func=func)

        if not download and func:
            return func(failed=True)

        # Extract component archive
        if manifest["File"][0]["rename"]:
            archive = manifest["File"][0]["rename"]
        else:
            archive = manifest["File"][0]["file_name"]

        self.extract_component(component_type, archive)

        # Empty the component lists and repopulate
        if component_type in ["runner", "runner:proton"]:
            self.runners_available = []
            self.check_runners()

        if component_type == "dxvk":
            self.dxvk_available = []
            self.check_dxvk()

        if component_type == "vkd3d":
            self.vkd3d_available = []
            self.check_vkd3d()

        # Execute a method at the end if passed
        if after:
            GLib.idle_add(after)

        # Re-populate local lists
        self.fetch_components()

    def install_component(self, component_type: str, component_name: str, after=False, func=False, checks=True) -> None:
        if self.utils_conn.check_connection(True):
            RunAsync(self.async_install_component, None, [
                     component_type, component_name, after, func, checks])
    '''
    Method for dependency installations
    '''

    def async_install_dependency(self, args: list) -> bool:
        configuration, dependency, widget = args
        self.download_manager = DownloadManager(self.window)
        has_no_uninstaller = False
        download_entry = self.download_manager.new_download(
            dependency[0], False)

        if configuration["Versioning"]:
            self.versioning_manager.async_create_bottle_state([
                configuration,
                f"before {dependency[0]}",
                True, False, None
            ])

        logging.info(
            f"Installing dependency: [{dependency[0]}] in bottle: [{configuration['Name']}].")

        # Get dependency manifest
        dependency_manifest = self.fetch_dependency_manifest(
            dependency[0],
            dependency[1]["Category"])

        # Execute installation steps
        for step in dependency_manifest.get("Steps"):

            # Step type: delete_sys32_dlls
            if step["action"] == "delete_sys32_dlls":
                for dll in step["dlls"]:
                    try:
                        logging.info(
                            f"Removing [{dll}] from system32 in bottle: [{configuration['Name']}]")
                        os.remove("%s/%s/drive_c/windows/system32/%s" % (
                            Paths.bottles, configuration.get("Name"), dll))
                    except FileNotFoundError:
                        logging.error(
                            f"[{dll}] not found in bottle: [{configuration['Name']}], failed removing from system32.")

            # Step type: install_exe, install_msi
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

                    Runner().run_executable(
                        configuration=configuration,
                        file_path=f"{Paths.temp}/{file}",
                        arguments=step.get("arguments"),
                        environment=step.get("environment"),
                        no_async=True)
                else:
                    if widget is not None:
                        widget.btn_install.set_sensitive(True)
                    return False

            # Step type: uninstall
            if step["action"] == "uninstall":
                file_name = step["file_name"]
                command = f"uninstaller --list | grep '{file_name}' | cut -f1 -d\|"

                uuid = Runner().run_command(
                    configuration=configuration,
                    command=command,
                    terminal=False,
                    environment=False,
                    comunicate=True)
                uuid = uuid.strip()

                if uuid != "":
                    logging.info(
                        f"Uninstalling [{file_name}] from bottle: [{configuration['Name']}].")
                    Runner().run_uninstaller(configuration, uuid)

            # Step type: cab_extract
            if step["action"] == "cab_extract":
                has_no_uninstaller = True  # cab extracted has no uninstaller

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

                        if not CabExtract().run(
                            f"{Paths.temp}/{file}",
                            file
                        ):
                            if widget is not None:
                                GLib.idle_add(widget.set_err)
                            exit()
                        if not CabExtract().run(
                            f"{Paths.temp}/{file}",
                            os.path.splitext(f"{file}")[0]
                        ):
                            if widget is not None:
                                GLib.idle_add(widget.set_err)
                            exit()

                elif step["url"].startswith("temp/"):
                    path = step["url"]
                    path = path.replace("temp/", f"{Paths.temp}/")

                    if step.get("rename"):
                        file_path = os.path.splitext(
                            f"{step.get('rename')}")[0]
                    else:
                        file_path = os.path.splitext(
                            f"{step.get('file_name')}")[0]

                    if not CabExtract().run(
                        f"{path}/{step.get('file_name')}",
                        file_path
                    ):
                        if widget is not None:
                            GLib.idle_add(widget.set_err)
                        exit()

            # Step type: archive_extract
            if step["action"] == "archive_extract":
                has_no_uninstaller = True  # extracted archives has no uninstaller

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

                        archive_name = os.path.splitext(file)[0]

                        if os.path.exists(f"{Paths.temp}/{archive_name}"):
                            shutil.rmtree(
                                f"{Paths.temp}/{archive_name}")

                        os.makedirs(f"{Paths.temp}/{archive_name}")
                        patoolib.extract_archive(
                            f"{Paths.temp}/{file}",
                            outdir=f"{Paths.temp}/{archive_name}")

            # Step type: install_cab_fonts
            if step["action"] in ["install_cab_fonts", "install_fonts"]:
                has_no_uninstaller = True  # cab extracted has no uninstaller

                path = step["url"]
                path = path.replace("temp/", f"{Paths.temp}/")
                bottle_path = Runner().get_bottle_path(configuration)

                for font in step.get('fonts'):
                    shutil.copyfile(
                        f"{path}/{font}",
                        f"{bottle_path}/drive_c/windows/Fonts/{font}")

            # Step type: copy_cab_dll
            if step["action"] in ["copy_cab_dll", "copy_dll"]:
                has_no_uninstaller = True  # cab extracted has no uninstaller

                path = step["url"]
                path = path.replace("temp/", f"{Paths.temp}/")
                bottle_path = Runner().get_bottle_path(configuration)

                try:
                    if "*" in step.get('file_name'):
                        files = glob(f"{path}/{step.get('file_name')}")
                        for fg in files:
                            shutil.copyfile(
                                fg,
                                f"{bottle_path}/drive_c/{step.get('dest')}/{os.path.basename(fg)}")
                    else:
                        shutil.copyfile(
                            f"{path}/{step.get('file_name')}",
                            f"{bottle_path}/drive_c/{step.get('dest')}")

                except FileNotFoundError:
                    logging.error(
                        f"dll {step.get('file_name')} not found in temp directory, there should be other errors from cabextract.")
                    break

            # Step type: override_dll
            if step["action"] == "override_dll":
                if step.get("url") and step.get("url").startswith("temp/"):
                    path = step["url"].replace(
                        "temp/", f"{Paths.temp}/")
                    path = f"{path}/{step.get('dll')}"

                    for dll in glob(path):
                        dll_name = os.path.splitext(os.path.basename(dll))[0]
                        self.reg_add(
                            configuration,
                            key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                            value=dll_name,
                            data=step.get("type"))
                else:
                    self.reg_add(
                        configuration,
                        key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                        value=step.get("dll"),
                        data=step.get("type"))

            # Step type: set_register_key
            if step["action"] == "set_register_key":
                self.reg_add(
                    configuration,
                    key=step.get("key"),
                    value=step.get("value"),
                    data=step.get("data"),
                    keyType=step.get("type"))

            # Step type: register_font
            if step["action"] == "register_font":
                self.reg_add(
                    configuration,
                    key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts",
                    value=step.get("name"),
                    data=step.get("file"))

        # Add dependency to bottle configuration
        if dependency[0] not in configuration.get("Installed_Dependencies"):
            dependencies = [dependency[0]]
            if configuration.get("Installed_Dependencies"):
                dependencies = configuration["Installed_Dependencies"] + \
                    [dependency[0]]

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

            if has_no_uninstaller:
                self.update_configuration(
                    configuration,
                    dependency[0],
                    "NO_UNINSTALLER",
                    "Uninstallers")

        # Remove entry from download manager
        GLib.idle_add(download_entry.remove)

        # Hide installation button and show remove button
        if widget is not None:
            if has_no_uninstaller:
                GLib.idle_add(widget.set_installed, False)
            else:
                GLib.idle_add(widget.set_installed, True)

        return True

    def install_dependency(self, configuration: BottleConfig, dependency: list, widget: Gtk.Widget = None) -> None:
        if self.utils_conn.check_connection(True):
            RunAsync(self.async_install_dependency, None, [configuration,
                                                           dependency,
                                                           widget])

    def remove_dependency(self, configuration: BottleConfig, dependency: list, widget: Gtk.Widget) -> None:
        logging.info(
            f"Removing dependency: [{ dependency[0]}] from bottle: [{configuration['Name']}] configuration.")

        uuid = False

        # Run uninstaller
        if dependency[0] in configuration["Uninstallers"]:
            uninstaller = configuration["Uninstallers"][dependency[0]]
            command = f"uninstaller --list | grep '{uninstaller}' | cut -f1 -d\|"
            uuid = Runner().run_command(
                configuration=configuration,
                command=command,
                terminal=False,
                environment=False,
                comunicate=True)
            uuid = uuid.strip()

        Runner().run_uninstaller(configuration, uuid)

        # Remove dependency from bottle configuration
        configuration["Installed_Dependencies"].remove(dependency[0])
        self.update_configuration(configuration,
                                  "Installed_Dependencies",
                                  configuration["Installed_Dependencies"])

        # Show installation button and hide remove button
        GLib.idle_add(widget.btn_install.set_visible, True)
        GLib.idle_add(widget.btn_remove.set_visible, False)

    def remove_program(self, configuration: BottleConfig, program_name: str):
        logging.info(
            f"Removing program: [{ program_name }] from bottle: [{configuration['Name']}] configuration.")

        uuid = False

        # Run uninstaller
        command = f"uninstaller --list | grep '{program_name}' | cut -f1 -d\|"
        uuid = Runner().run_command(
            configuration=configuration,
            command=command,
            terminal=False,
            environment=False,
            comunicate=True)
        uuid = uuid.strip()

        Runner().run_uninstaller(configuration, uuid)

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
                    self.install_component("runner", runner_name, after=after)
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
                        self.async_install_component(
                            ["dxvk", dxvk_version, False, False, False])
                    else:
                        self.install_component(
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
                        self.async_install_component(
                            ["vkd3d", vkd3d_version, False, False, False])
                    else:
                        self.install_component(
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

    def __get_exe_parent_dir(self, configuration, executable_path):
        p = ""
        if "\\" in executable_path:
            p = "\\".join(executable_path.split("\\")[:-1])
            p = p.replace("C:\\", "\\drive_c\\").replace("\\", "/")
            return Runner().get_bottle_path(configuration) + p

        p = "\\".join(executable_path.split("/")[:-1])
        p = f"/drive_c/{p}"
        return p.replace("\\", "/")

    # Get installed programs
    def get_programs(self, configuration: BottleConfig) -> list:
        '''TODO: Programs found should be stored in a database
        TN: Will be fixed in Trento release'''
        bottle = "%s/%s" % (Paths.bottles, configuration.get("Path"))
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
                        configuration, executable_path)

                    icon = self.__find_program_icon(executable_name)
                    installed_programs.append(
                        [path, executable_path, icon, program_folder])
            except:
                pass

        if configuration.get("External_Programs"):
            ext_programs = configuration.get("External_Programs")
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

    # Fetch installer manifest
    def fetch_installer_manifest(self, installer_name: str, installer_category: str, plain: bool = False) -> Union[str, dict, bool]:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen("%s/%s/%s.yml" % (
                BottlesRepositories.installers,
                installer_category,
                installer_name
            )) as url:
                if plain:
                    return url.read().decode("utf-8")
                return yaml.safe_load(url.read())
        return False

    # Fetch components
    def fetch_components(self) -> bool:
        if not self.utils_conn.check_connection():
            return False

        try:
            url = urllib.request.urlopen(BottlesRepositories.components_index)
            index = yaml.safe_load(url.read())

            for component in index.items():
                if component[1]["Category"] == "runners":
                    '''
                    Hide the lutris-lol runner if Bottles is running as Flatpak
                    because it is not compatible under sandbox
                    https://github.com/bottlesdevs/components/issues/54
                    '''
                    if "FLATPAK_ID" in os.environ and "-lol" in component[0]:
                        continue

                    if component[1]["Sub-category"] == "wine":
                        self.supported_wine_runners[component[0]
                                                    ] = component[1]
                        if component[0] in self.runners_available:
                            self.supported_wine_runners[component[0]
                                                        ]["Installed"] = True

                    if component[1]["Sub-category"] == "proton":
                        self.supported_proton_runners[component[0]
                                                    ] = component[1]
                        if component[0] in self.runners_available:
                            self.supported_proton_runners[component[0]
                                                        ]["Installed"] = True

                if component[1]["Category"] == "dxvk":
                    self.supported_dxvk[component[0]] = component[1]
                    if component[0] in self.dxvk_available:
                        self.supported_dxvk[component[0]
                                            ]["Installed"] = True

                if component[1]["Category"] == "vkd3d":
                    self.supported_vkd3d[component[0]] = component[1]
                    if component[0] in self.vkd3d_available:
                        self.supported_vkd3d[component[0]
                                            ]["Installed"] = True
            url.close()
            return True
        except:
            logging.error(f"Cannot fetch components list.")
            return False

    # Fetch component manifest
    def fetch_component_manifest(self, component_type: str, component_name: str, plain: bool = False) -> Union[str, dict, bool]:
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
                    BottlesRepositories.components,
                    component["Category"],
                    component["Sub-category"],
                    component_name)
            else:
                manifest_url = "%s/%s/%s.yml" % (
                    BottlesRepositories.components,
                    component["Category"],
                    component_name)
            try:
                with urllib.request.urlopen(manifest_url) as url:
                    if plain:
                        return url.read().decode("utf-8")
                    return yaml.safe_load(url.read())
            except:
                logging.error(f"Cannot fetch manifest for {component_name}.")
                return False
        
        return False
                

    # Fetch dependencies
    def fetch_dependencies(self) -> bool:
        if not self.utils_conn.check_connection():
            return False

        try:
            url = urllib.request.urlopen(BottlesRepositories.dependencies_index)
            index = yaml.safe_load(url.read())

            for dependency in index.items():
                self.supported_dependencies[dependency[0]] = dependency[1]
            return True
        except:
            logging.error(F"Cannot fetch dependencies list.")
            return False

    # Fetch dependency manifest
    def fetch_dependency_manifest(self, dependency_name: str, dependency_category: str, plain: bool = False) -> Union[str, dict, bool]:
        if self.utils_conn.check_connection():
            with urllib.request.urlopen("%s/%s/%s.yml" % (
                BottlesRepositories.dependencies,
                dependency_category,
                dependency_name
            )) as url:
                if plain:
                    return url.read().decode("utf-8")
                return yaml.safe_load(url.read())

        return False

    # Check Bottles data from old directory (only Flatpak)
    def check_bottles_n(self):
        data = glob(f"{base_path_n}/*")
        return len(data)

    # Check local bottles
    def check_bottles(self, silent: bool = False) -> None:
        bottles = glob("%s/*/" % Paths.bottles)

        '''
        For each bottle add the path name to the `local_bottles` variable
        and append the configuration
        '''
        for bottle in bottles:
            bottle_name_path = bottle.split("/")[-2]

            try:
                conf_file = open(f"{bottle}/bottle.yml")
                conf_file_yaml = yaml.safe_load(conf_file)
                conf_file.close()
                
                # Update architecture of old bottles
                if conf_file_yaml.get("Arch") in ["", None]:
                    self.update_configuration(conf_file_yaml,
                                              "Arch",
                                              Samples.configuration["Arch"])

                miss_keys = Samples.configuration.keys() - conf_file_yaml.keys()
                for key in miss_keys:
                    logging.warning(
                        f"Key: [{key}] not in bottle: [{bottle.split('/')[-2]}] configuration, updating.")
                    self.update_configuration(conf_file_yaml,
                                              key,
                                              Samples.configuration[key],
                                              no_update=True)

                miss_params_keys = Samples.configuration["Parameters"].keys(
                ) - conf_file_yaml["Parameters"].keys()
                for key in miss_params_keys:
                    logging.warning(
                        f"Key: [{key}] not in bottle: [{bottle.split('/')[-2]}] configuration Parameters, updating.")
                    self.update_configuration(conf_file_yaml,
                                              key,
                                              Samples.configuration["Parameters"][key],
                                              scope="Parameters",
                                              no_update=True)
                self.local_bottles[bottle_name_path] = conf_file_yaml

            except FileNotFoundError:
                new_configuration_yaml = Samples.configuration.copy()
                new_configuration_yaml["Broken"] = True
                new_configuration_yaml["Name"] = bottle_name_path
                new_configuration_yaml["Environment"] = "Undefined"
                self.local_bottles[bottle_name_path] = new_configuration_yaml

        if len(self.local_bottles) > 0 and not silent:
            logging.info(f"Bottles found: {'|'.join(self.local_bottles)}")

    # Update parameters in bottle configuration
    def update_configuration(self, configuration: BottleConfig, key: str, value: str, scope: str = "", no_update: bool = False, remove: bool = False) -> dict:
        logging.info(
            f"Setting Key: [{key}] to [{value}] for bottle: [{configuration['Name']}] …")

        bottle_complete_path = Runner().get_bottle_path(configuration)

        if scope != "":
            configuration[scope][key] = value
            if remove:
                del configuration[scope][key]
        else:
            configuration[key] = value
            if remove:
                del configuration[key]

        with open("%s/bottle.yml" % bottle_complete_path,
                  "w") as conf_file:
            yaml.dump(configuration, conf_file, indent=4)
            conf_file.close()

        if not no_update:
            self.update_bottles(silent=True)

        # Update Update_Date in configuration
        configuration["Update_Date"] = str(datetime.now())
        return configuration

    # Create new wineprefix
    def async_create_bottle(self, args: list) -> None:
        logging.info("Creating the wineprefix …")

        name, environment, path, manager, dxvk, vkd3d, versioning, dialog, arch = args

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
        update_output(_("The wine configuration is being updated …"))
        command = "DISPLAY=:3.0 WINEDEBUG=fixme-all WINEPREFIX={path} WINEARCH={arch} {runner} wineboot /nogui".format(
            path=bottle_complete_path,
            arch=arch,
            runner=runner
        )
        subprocess.Popen(command, shell=True).communicate()
        update_output(_("Wine configuration updated!"))
        time.sleep(1)

        # Generate bottle configuration file
        logging.info("Generating Bottle configuration file …")
        update_output(_("Generating Bottle configuration file …"))

        configuration = Samples.configuration
        configuration["Name"] = bottle_name
        configuration["Arch"] = arch
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
        if versioning:
            configuration["Versioning"] = True

        # Apply environment configuration
        logging.info(f"Applying environment: [{environment}] …")
        update_output(_("Applying environment: {0} …").format(environment))
        if environment != "Custom":
            environment_parameters = Samples.environments[environment.lower(
            )]["Parameters"]
            for parameter in configuration["Parameters"]:
                if parameter in environment_parameters:
                    configuration["Parameters"][parameter] = environment_parameters[parameter]

        time.sleep(1)

        # Save bottle configuration
        with open(f"{bottle_complete_path}/bottle.yml", "w") as conf_file:
            yaml.dump(configuration, conf_file, indent=4)
            conf_file.close()

        time.sleep(5)

        # Perform dxvk installation if configured
        if configuration["Parameters"]["dxvk"]:
            logging.info("Installing dxvk …")
            update_output(_("Installing dxvk …"))
            self.install_dxvk(configuration, version=dxvk_name)

        # Perform vkd3d installation if configured
        if configuration["Parameters"]["vkd3d"]:
            logging.info("Installing vkd3d …")
            update_output(_("Installing vkd3d …"))
            self.install_vkd3d(configuration, version=vkd3d_name)

        time.sleep(1)

        # Create first state if versioning enabled
        if versioning:
            logging.info("Creating versioning state 0 …")
            update_output(_("Creating versioning state 0 …"))
            self.versioning_manager.async_create_bottle_state(
                [configuration, "First boot", False, True, False])

        # Set status created and UI usability
        logging.info(f"Bottle: [{bottle_name}] successfully created!")
        update_output(
            _("Your new bottle: {0} is now ready!").format(bottle_name))

        time.sleep(2)

        dialog.finish(configuration)

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
    def get_bottle_size(self, configuration: BottleConfig, human: bool = True) -> Union[str, float]:
        path = configuration.get("Path")

        if not configuration.get("Custom_Path"):
            path = "%s/%s" % (Paths.bottles, path)

        return self.get_path_size(path, human)

    # Delete a wineprefix
    def async_delete_bottle(self, args: list) -> bool:
        logging.info("Deleting a bottle …")

        configuration = args[0]

        if configuration.get("Path"):
            logging.info(f"Removing applications installed with the bottle ..")
            for inst in glob(f"{Paths.applications}/{configuration.get('Name')}--*"):
                os.remove(inst)

            logging.info(f"Removing the bottle ..")
            if not configuration.get("Custom_Path"):
                path = "%s/%s" % (Paths.bottles,
                                  configuration.get("Path"))

            shutil.rmtree(path)
            del self.local_bottles[configuration.get("Path")]

            logging.info(f"Successfully deleted bottle in path: [{path}]")
            self.window.page_list.update_bottles()

            return True

        logging.error("Empty path found, failing to avoid disasters.")
        return False

    def delete_bottle(self, configuration: BottleConfig) -> None:
        RunAsync(self.async_delete_bottle, None, [configuration])

    #  Repair a bottle generating a new configuration
    def repair_bottle(self, configuration: BottleConfig) -> bool:
        logging.info(
            f"Trying to repair the bottle: [{configuration['Name']}] …")

        bottle_complete_path = f"{Paths.bottles}/{configuration['Name']}"

        # Create new configuration with path as name and Custom environment
        new_configuration = Samples.configuration
        new_configuration["Name"] = configuration.get("Name")
        new_configuration["Runner"] = self.runners_available[0]
        new_configuration["Path"] = configuration.get("Name")
        new_configuration["Environment"] = "Custom"
        new_configuration["Creation_Date"] = str(datetime.now())
        new_configuration["Update_Date"] = str(datetime.now())

        try:
            with open("%s/bottle.yml" % bottle_complete_path,
                      "w") as conf_file:
                yaml.dump(new_configuration, conf_file, indent=4)
                conf_file.close()
        except:
            return False

        # Execute wineboot in bottle to generate missing files
        Runner().run_wineboot(new_configuration)

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
    def reg_add(self, configuration: BottleConfig, key: str, value: str, data: str, keyType: str = False) -> None:
        logging.info(
            f"Adding Key: [{key}] with Value: [{value}] and Data: [{data}] in register bottle: {configuration['Name']}")

        command = "reg add '%s' /v '%s' /d %s /f" % (key, value, data)

        if keyType:
            command = "reg add '%s' /v '%s' /t %s /d %s /f" % (
                key, value, keyType, data)

        Runner().run_command(configuration, command)

    # Remove key from register
    def reg_delete(self, configuration: BottleConfig, key: str, value: str) -> None:
        logging.info(
            f"Removing Value: [{key}] for Key: [{value}] in register bottle: {configuration['Name']}")

        Runner().run_command(configuration, "reg delete '%s' /v %s /f" % (
            key, value))

    '''
    Install dxvk using official script
    TODO: A good task for the future is to use the built-in methods
    to install the new dlls and register the override for dxvk.
    '''

    def install_dxvk(self, configuration: BottleConfig, remove: bool = False, version: str = False) -> bool:
        logging.info(f"Installing dxvk for bottle: [{configuration['Name']}].")

        if version:
            dxvk_version = version
        else:
            dxvk_version = configuration.get("DXVK")

        option = "uninstall" if remove else "install"

        command = 'DISPLAY=:3.0 WINEPREFIX="{path}" PATH="{runner}:$PATH" {dxvk_setup} {option} --with-d3d10'.format(
            path="%s/%s" % (Paths.bottles, configuration.get("Path")),
            runner="%s/%s/bin" % (Paths.runners,
                                  configuration.get("Runner")),
            dxvk_setup="%s/%s/setup_dxvk.sh" % (
                Paths.dxvk, dxvk_version),
            option=option)

        return subprocess.Popen(command, shell=True).communicate()

    '''
    Install vkd3d using official script
    '''

    def install_vkd3d(self, configuration: BottleConfig, remove: bool = False, version: str = False) -> bool:
        logging.info(
            f"Installing vkd3d for bottle: [{configuration['Name']}].")

        if version:
            vkd3d_version = version
        else:
            vkd3d_version = configuration.get("VKD3D")

        if not vkd3d_version:
            vkd3d_version = self.vkd3d_available[0]
            self.update_configuration(configuration, "VKD3D", vkd3d_version)

        option = "uninstall" if remove else "install"

        command = 'DISPLAY=:3.0 WINEPREFIX="{path}" PATH="{runner}:$PATH" {vkd3d_setup} {option}'.format(
            path="%s/%s" % (Paths.bottles, configuration.get("Path")),
            runner="%s/%s/bin" % (Paths.runners,
                                  configuration.get("Runner")),
            vkd3d_setup="%s/%s/setup_vkd3d_proton.sh" % (
                Paths.vkd3d, vkd3d_version),
            option=option)

        return subprocess.Popen(command, shell=True).communicate()

    # Remove dxvk using official script
    def remove_dxvk(self, configuration: BottleConfig) -> None:
        logging.info(f"Removing dxvk for bottle: [{configuration['Name']}].")

        self.install_dxvk(configuration, remove=True)

    # Remove vkd3d using official script
    def remove_vkd3d(self, configuration: BottleConfig) -> None:
        logging.info(f"Removing vkd3d for bottle: [{configuration['Name']}].")

        self.install_vkd3d(configuration, remove=True)

    # Override dlls in system32/syswow64 paths
    def dll_override(self, configuration: BottleConfig, arch: str, dlls: list, source: str, revert: bool = False) -> bool:
        arch = "system32" if arch == 32 else "syswow64"
        path = "%s/%s/drive_c/windows/%s" % (Paths.bottles,
                                             configuration.get("Path"),
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
    def toggle_virtual_desktop(self, configuration: BottleConfig, state: bool, resolution: str = "800x600") -> None:
        key = "HKEY_CURRENT_USER\\Software\\Wine\\Explorer\\Desktops"
        if state:
            self.reg_add(configuration, key, "Default", resolution)
        else:
            self.reg_delete(configuration, key, "Default")

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

        # Create bottle configuration
        new_configuration = Samples.configuration
        new_configuration["Name"] = wineprefix["Name"]
        new_configuration["Runner"] = self.get_latest_runner()
        new_configuration["Path"] = bottle_path
        new_configuration["Environment"] = "Custom"
        new_configuration["Creation_Date"] = str(datetime.now())
        new_configuration["Update_Date"] = str(datetime.now())

        # Save configuration
        with open("%s/bottle.yml" % bottle_complete_path,
                  "w") as conf_file:
            yaml.dump(new_configuration, conf_file, indent=4)
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
