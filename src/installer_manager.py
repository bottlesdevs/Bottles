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
import urllib.request
from typing import NewType
from datetime import datetime
from gi.repository import Gtk, GLib

from .runner_utilities import RunnerUtilities
from .runner_globals import BottlesRepositories, BottlesPaths
from .utils import RunAsync

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)

class InstallerManager:

    def __init__(self, runner, configuration:BottleConfig, installer:list, widget:Gtk.Widget=None):
        self.runner = runner
        self.configuration = configuration
        self.manifest = self.runner.fetch_installer_manifest(
            installer_name = installer[0],
            installer_category = installer[1]["Category"])
        self.widget = widget
        self.runner_utils = RunnerUtilities(self.configuration)
        self.bottle_icons_path = f"{self.runner_utils.get_bottle_path(configuration)}/icons"

    def __download_icon(self, executable:dict):
        icon_url = f"{BottlesRepositories.installers}/data/{self.manifest.get('Name')}/{executable.get('icon')}"
        icon_path = f"{self.bottle_icons_path}/{executable.get('icon')}"

        if not os.path.exists(self.bottle_icons_path):
            os.makedirs(self.bottle_icons_path)
        if not os.path.isfile(icon_path):
            urllib.request.urlretrieve(icon_url, icon_path)

    def __install_dependencies(self, dependencies:list):
        for dep in dependencies:
            if dep in self.configuration.get("Installed_Dependencies"):
                continue
            dep_index = [dep, self.runner.supported_dependencies.get(dep)]
            self.runner.async_install_dependency([self.configuration, dep_index, None])

    def __perform_steps(self, steps:list):
        for st in steps:
            # Step type: install_exe, install_msi
            if st["action"] in ["install_exe", "install_msi"]:
                download = self.runner.download_component(
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

                    self.runner_utils.run_executable(
                        configuration=self.configuration,
                        file_path=f"{BottlesPaths.temp}/{file}",
                        arguments=st.get("arguments"),
                        environment=st.get("environment"))
    
    def __set_parameters(self, parameters:dict):
        if parameters.get("dxvk") and not self.configuration.get("Parameters")["dxvk"]:
            self.runner.install_dxvk(self.configuration)

        if parameters.get("vkd3d") and self.configuration.get("Parameters")["vkd3d"]:
            self.runner.install_vkd3d(self.configuration)

        for param in parameters:
            self.runner.update_configuration(
                configuration=self.configuration,
                key=param,
                value=parameters[param],
                scope="Parameters")

    def __set_executable_arguments(self, executable:dict):
        self.runner.update_configuration(
            configuration=self.configuration,
            key=executable.get("file"),
            value=executable.get("arguments"),
            scope="Programs")

    def __create_desktop_entry(self, executable:dict):
        icon_path = f"{self.bottle_icons_path}/{executable.get('icon')}"
        desktop_file = f"{BottlesPaths.applications}/{self.configuration.get('Name')}--{self.manifest.get('Name')}--{datetime.now().timestamp()}.desktop"

        if "IS_FLATPAK" in os.environ:
            return None
            
        with open(desktop_file, "w") as f:
            ex_path = f"{BottlesPaths.bottles}/{self.configuration.get('Path')}/drive_c/{executable.get('path')}/{executable.get('file')}"
            f.write(f"[Desktop Entry]\n")
            f.write(f"Name={executable.get('name')}\n")
            f.write(f"Exec=bottles -e '{ex_path}' -b '{self.configuration.get('Name')}'\n")
            f.write(f"Type=Application\n")
            f.write(f"Terminal=false\n")
            f.write(f"Categories=Application;\n")
            if executable.get("icon"):
                f.write(f"Icon={icon_path}\n")
            else:
                f.write(f"Icon=com.usebottles.bottles")
            f.write(f"Comment={self.manifest.get('Description')}\n")
            # Actions
            f.write("Actions=Configure;\n")
            f.write("[Desktop Action Configure]\n")
            f.write("Name=Configure in Bottles\n")
            f.write(f"Exec=bottles -b '{self.configuration.get('Name')}'\n")
    
    def __async_install(self) -> None:
        dependencies = self.manifest.get("Dependencies")
        parameters = self.manifest.get("Parameters")
        executable = self.manifest.get("Executable")
        steps = self.manifest.get("Steps")

        # download icon
        if executable.get("icon"):
            self.__download_icon(executable)
        
        # install dependencies
        if dependencies:
            self.__install_dependencies(dependencies)
        
        if steps:
            self.__perform_steps(steps)
        
        # set parameters
        if parameters:
            self.__set_parameters(parameters)

        # register executable arguments
        if executable.get("arguments"):
            self.__set_executable_arguments(executable)

        # create Desktop entry
        self.__create_desktop_entry(executable)

        # unlock widget
        if self.widget is not None:
            GLib.idle_add(self.widget.set_installed)
    
    def install(self) -> None:
        RunAsync(self.__async_install, False)