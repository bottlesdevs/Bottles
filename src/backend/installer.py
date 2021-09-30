# installer_manager.py
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
import urllib.request
from typing import Union, NewType
from datetime import datetime
from gi.repository import Gtk, GLib

from .runner import Runner
from .globals import BottlesRepositories, Paths
from ..utils import RunAsync, UtilsLogger

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)

class InstallerManager:

    def __init__(
        self, 
        manager,
        widget:Gtk.Widget=None
    ):
        self.__manager = manager
        self.__utils_conn = manager.utils_conn
        self.__component_manager = manager.component_manager

    def get_installer(
        self, 
        installer_name: str, 
        installer_category: str, 
        plain: bool = False
    ) -> Union[str, dict, bool]:
        '''
        This function can be used to fetch the manifest for a given
        installer. It can be returned as plain text or as a dictionary.
        It will return False if the installer is not found.
        '''
        if self.__utils_conn.check_connection():
            try:
                with urllib.request.urlopen("%s/%s/%s.yml" % (
                    BottlesRepositories.installers,
                    installer_category,
                    installer_name
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
                logging.error(f"Cannot fetch manifest for {installer_name}.")
                return False

        return False

    def __download_icon(self, config, executable:dict, manifest):
        icon_url = "%s/data/%s/%s" % (
            BottlesRepositories.installers,
            manifest.get('Name'),
            executable.get('icon')
        )
        bottle_icons_path = f"{Runner().get_bottle_path(config)}/icons"
        icon_path = f"{bottle_icons_path}/{executable.get('icon')}"

        if not os.path.exists(bottle_icons_path):
            os.makedirs(bottle_icons_path)
        if not os.path.isfile(icon_path):
            urllib.request.urlretrieve(icon_url, icon_path)

    def __install_dependencies(
        self, 
        config, 
        dependencies:list, 
        widget:Gtk.Widget
    ):
        for dep in dependencies:
            widget.next_step()

            if dep in config.get("Installed_Dependencies"):
                continue

            dep_index = [dep, self.__manager.supported_dependencies.get(dep)]
            self.__manager.dependency_manager.async_install([
                config, 
                dep_index, 
                None
            ])

    def __perform_steps(self, config, steps:list):
        for st in steps:
            # Step type: install_exe, install_msi
            if st["action"] in ["install_exe", "install_msi"]:
                download = self.__component_manager.download(
                    "installer",
                    st.get("url"),
                    st.get("file_name"),
                    st.get("rename"),
                    checksum=st.get("file_checksum"))

                if download:
                    if st.get("rename"):
                        file = st.get("rename")
                    else:
                        file = st.get("file_name")

                    Runner().run_executable(
                        config=config,
                        file_path=f"{Paths.temp}/{file}",
                        arguments=st.get("arguments"),
                        environment=st.get("environment"))
    
    def __set_parameters(self, config, parameters:dict):
        if parameters.get("dxvk") and not config.get("Parameters")["dxvk"]:
            self.__manager.install_dxvk(config)

        if parameters.get("vkd3d") and config.get("Parameters")["vkd3d"]:
            self.__manager.install_vkd3d(config)

        for param in parameters:
            self.__manager.update_config(
                config=config,
                key=param,
                value=parameters[param],
                scope="Parameters"
            )

    def __set_executable_arguments(self, config, executable:dict):
        self.__manager.update_config(
            config=config,
            key=executable.get("file"),
            value=executable.get("arguments"),
            scope="Programs")

    def __create_desktop_entry(self, config, manifest, executable:dict):
        bottle_icons_path = f"{Runner().get_bottle_path(config)}/icons"

        icon_path = f"{bottle_icons_path}/{executable.get('icon')}"
        desktop_file = "%s/%s--%s--%s.desktop" % (
            Paths.applications,
            config.get('Name'),
            manifest.get('Name'),
            datetime.now().timestamp()
        )

        if "FLATPAK_ID" in os.environ:
            return None
            
        with open(desktop_file, "w") as f:
            ex_path = "%s/%s/drive_c/%s/%s" % (
                Paths.bottles,
                config.get('Path'),
                executable.get('path'),
                executable.get('file')
            )
            f.write(f"[Desktop Entry]\n")
            f.write(f"Name={executable.get('name')}\n")
            f.write(f"Exec=bottles -e '{ex_path}' -b '{config.get('Name')}'\n")
            f.write(f"Type=Application\n")
            f.write(f"Terminal=false\n")
            f.write(f"Categories=Application;\n")
            if executable.get("icon"):
                f.write(f"Icon={icon_path}\n")
            else:
                f.write(f"Icon=com.usebottles.bottles")
            f.write(f"Comment={manifest.get('Description')}\n")
            # Actions
            f.write("Actions=Configure;\n")
            f.write("[Desktop Action Configure]\n")
            f.write("Name=Configure in Bottles\n")
            f.write(f"Exec=bottles -b '{config.get('Name')}'\n")
    
    def __async_install(self, args) -> None:
        config, installer, widget = args

        manifest = self.get_installer(
            installer_name = installer[0],
            installer_category = installer[1]["Category"]
        )
        steps = 0
        if manifest.get("Dependencies"):
            steps += int(len(manifest.get("Dependencies")))
        if manifest.get("Parameters"):
            steps += 1
        if manifest.get("Steps"):
            steps += int(len(manifest.get("Steps")))
        if manifest.get("Executable"):
            steps += 1
        widget.set_steps(steps)
        
        dependencies = manifest.get("Dependencies")
        parameters = manifest.get("Parameters")
        executable = manifest.get("Executable")
        steps = manifest.get("Steps")

        # download icon
        if executable.get("icon"):
            self.__download_icon(config, executable, manifest)
        
        # install dependencies
        if dependencies:
            self.__install_dependencies(config, dependencies, widget)
        
        # execute steps
        if steps:
            widget.next_step()
            self.__perform_steps(config, steps)
        
        # set parameters
        if parameters:
            widget.next_step()
            self.__set_parameters(config, parameters)

        # register executable arguments
        if executable.get("arguments"):
            self.__set_executable_arguments(config, executable)

        # create Desktop entry
        widget.next_step()
        self.__create_desktop_entry(config, manifest, executable)

        # unlock widget
        if widget is not None:
            GLib.idle_add(widget.set_installed)
    
    def install(self, config, installer, widget) -> None:
        RunAsync(self.__async_install, False, [config, installer, widget])