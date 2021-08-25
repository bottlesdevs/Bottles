# dependency.py
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
import yaml
import shutil
import patoolib
from glob import glob
import urllib.request
from typing import Union, NewType
from gi.repository import Gtk, GLib

from ..download import DownloadManager
from .runner import Runner
from .globals import BottlesRepositories, Paths
from ..utils import RunAsync, UtilsLogger, CabExtract, validate_url

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)

class DependencyManager:

    def __init__(self, manager):
        self.__manager = manager
        self.__window = manager.window
        self.__utils_conn = manager.utils_conn
        self.__download_manager = DownloadManager(self.__window)

    def get_dependency(
        self, 
        dependency_name: str, 
        dependency_category: str, 
        plain: bool = False
    ) -> Union[str, dict, bool]:
        '''
        This function can be used to fetch the manifest for a given
        dependency. It can be returned as plain text or as a dictionary.
        It will return False if the dependency is not found.
        '''
        if self.__utils_conn.check_connection():
            try:
                with urllib.request.urlopen("%s/%s/%s.yml" % (
                    BottlesRepositories.dependencies,
                    dependency_category,
                    dependency_name
                )) as url:
                    if plain:
                        '''
                        Caller required the component manifest
                        as plain text.
                        '''
                        return url.read().decode("utf-8")

                    # return as dictionary
                    return yaml.safe_load(url.read())
            except:
                logging.error(f"Cannot fetch manifest for {dependency_name}.")
                return False

        return False

    def fetch_catalog(self) -> list:
        '''
        This function fetch all dependencies from the Bottles repository
        and return these as a dictionary. It also returns an empty dictionary
        if there are no dependencies or fails to fetch them.
        '''
        catalog = {}
        if not self.__utils_conn.check_connection():
            return {}

        try:
            with urllib.request.urlopen(
                BottlesRepositories.dependencies_index
            ) as url:
                index = yaml.safe_load(url.read())
        except:
            logging.error(F"Cannot fetch dependencies list.")
            return {}

        for dependency in index.items():
            catalog[dependency[0]] = dependency[1]
        return catalog

    def async_install(self, args: list) -> bool:
        '''
        This function install a given dependency in a bottle. It will
        return True if the installation was successful and update the
        widget status.
        '''
        configuration, dependency, widget = args
        has_no_uninstaller = False

        if configuration["Versioning"]:
            '''
            If the bottle has the versioning system enabled, we need
            to create a new version of the bottle, before installing
            the dependency.
            '''
            self.__manager.versioning_manager.async_create_bottle_state([
                configuration,
                f"before {dependency[0]}",
                True, False, None
            ])

        download_entry = self.__download_manager.new_download(
            file_name=dependency[0], 
            cancellable=False
        )

        logging.info(
            f"Installing dependency: [{dependency[0]}] in bottle: [{configuration['Name']}]."
        )
        manifest = self.get_dependency(
            dependency_name=dependency[0],
            dependency_category=dependency[1]["Category"]
        )
        if not manifest:
            '''
            If the manifest is not found, update the widget status to
            not installed and return False.
            '''
            GLib.idle_add(widget.set_installed, False)
            return False

        for step in manifest.get("Steps"):
            '''
            Here we execute all steps in the manifest.
            Steps are the actions performed to install the dependency.
            '''

            if step["action"] == "delete_sys32_dlls":
                self.__step_delete_sys32_dlls(
                    configuration=configuration,
                    dlls=step["dlls"]
                )

            if step["action"] in ["install_exe", "install_msi"]:
                self.__step_install_exe_msi(
                    configuration=configuration,
                    step=step,
                    widget=widget
                )

            if step["action"] == "uninstall":
                self.__step_uninstall(
                    configuration=configuration,
                    file_name=step["file_name"]
                )

            if step["action"] == "cab_extract":
                has_no_uninstaller = True
                self.__step_cab_extract(
                    step=step,
                    widget=widget
                )

            if step["action"] == "archive_extract":
                has_no_uninstaller = True
                self.__step_archive_extract(step)

            if step["action"] in ["install_cab_fonts", "install_fonts"]:
                has_no_uninstaller = True
                self.__step_install_fonts(
                    configuration=configuration,
                    step=step
                )

            if step["action"] in ["copy_cab_dll", "copy_dll"]:
                has_no_uninstaller = True
                self.__step_copy_dll(
                    configuration=configuration,
                    step=step
                )

            if step["action"] == "override_dll":
                self.__step_override_dll(
                    configuration=configuration,
                    step=step
                )

            if step["action"] == "set_register_key":
                self.set_register_key(
                    configuration=configuration,
                    step=step
                )

            if step["action"] == "register_font":
                self.__step_set_register_key(
                    configuration=configuration,
                    step=step
                )

        # Add dependency to bottle configuration
        if dependency[0] not in configuration.get("Installed_Dependencies"):
            dependencies = [dependency[0]]
            if configuration.get("Installed_Dependencies"):
                dependencies = configuration["Installed_Dependencies"] + \
                    [dependency[0]]

            self.__manager.update_configuration(
                configuration,
                "Installed_Dependencies",
                dependencies)

            if manifest.get("Uninstaller"):
                self.__manager.update_configuration(
                    configuration,
                    dependency[0],
                    manifest["Uninstaller"],
                    "Uninstallers")

            if has_no_uninstaller:
                self.__manager.update_configuration(
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

    def install(self, configuration: BottleConfig, dependency: list, widget: Gtk.Widget = None) -> None:
        if self.__utils_conn.check_connection(True):
            RunAsync(self.async_install, None, [
                    configuration,
                    dependency,
                    widget
                ]
            )
    
    def __step_delete_sys32_dlls(self, configuration: BottleConfig, dlls: list) -> None:
        for dll in dlls:
            try:
                logging.info(
                    f"Removing [{dll}] from system32 in bottle: [{configuration['Name']}]"
                )
                os.remove("%s/%s/drive_c/windows/system32/%s" % (
                    Paths.bottles, configuration.get("Name"), dll))
            except FileNotFoundError:
                logging.error(
                    f"[{dll}] not found in bottle: [{configuration['Name']}], failed removing from system32."
                )
    
    def __step_install_exe_msi(self, configuration:BottleConfig, step:dict, widget:Gtk.Widget) -> Union[None, bool]:
        download = self.__manager.component_manager.download(
            component="dependency",
            download_url=step.get("url"),
            file=step.get("file_name"),
            rename=step.get("rename"),
            checksum=step.get("file_checksum")
        )
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

    def __step_uninstall(self, configuration:BottleConfig, file_name:str) -> None:
        command = f"uninstaller --list | grep '{file_name}' | cut -f1 -d\|"

        uuid = Runner().run_command(
            configuration=configuration,
            command=command,
            terminal=False,
            environment=False,
            comunicate=True
        )
        uuid = uuid.strip()

        if uuid != "":
            logging.info(
                f"Uninstalling [{file_name}] from bottle: [{configuration['Name']}]."
            )
            Runner().run_uninstaller(configuration, uuid)
    
    def __step_cab_extract(self, step:dict, widget:Gtk.Widget) -> None: 
        if validate_url(step["url"]):
            download = self.__manager.component_manager.download(
                component="dependency",
                download_url=step.get("url"),
                file=step.get("file_name"),
                rename=step.get("rename"),
                checksum=step.get("file_checksum")
            )
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
    
    def __step_archive_extract(self, step:dict) -> None:
        download = self.__manager.component_manager.download(
            component="dependency",
            download_url=step.get("url"),
            file=step.get("file_name"),
            rename=step.get("rename"),
            checksum=step.get("file_checksum")
        )

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

    def __step_install_fonts(self, configuration:BottleConfig, step:dict) -> None:
        path = step["url"]
        path = path.replace("temp/", f"{Paths.temp}/")
        bottle_path = Runner().get_bottle_path(configuration)

        for font in step.get('fonts'):
            shutil.copyfile(
                f"{path}/{font}",
                f"{bottle_path}/drive_c/windows/Fonts/{font}")

    def __step_copy_dll(self, configuration:BottleConfig, step:dict) -> None:
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
            return False

    def __step_override_dll(self, configuration:BottleConfig, step:dict) -> None:
        if step.get("url") and step.get("url").startswith("temp/"):
            path = step["url"].replace(
                "temp/", f"{Paths.temp}/")
            path = f"{path}/{step.get('dll')}"

            for dll in glob(path):
                dll_name = os.path.splitext(os.path.basename(dll))[0]
                self.__manager.reg_add(
                    configuration,
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=dll_name,
                    data=step.get("type"))
            return

        self.__manager.reg_add(
            configuration,
            key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
            value=step.get("dll"),
            data=step.get("type"))

    def __step_set_register_key(self, configuration:BottleConfig, step:dict) -> None:
        self.__manager.reg_add(
            configuration,
            key=step.get("key"),
            value=step.get("value"),
            data=step.get("data"),
            keyType=step.get("type")
        )