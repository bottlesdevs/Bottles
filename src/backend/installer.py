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
import subprocess
import yaml
import markdown
import urllib.request
from typing import Union, NewType
from functools import lru_cache
from datetime import datetime
from gi.repository import Gtk, GLib

from .runner import Runner
from .manager_utils import ManagerUtils
from .globals import BottlesRepositories, Paths
from ..utils import RunAsync, UtilsLogger
from .layers import LayersStore, Layer

from bottles.backend.wine.wineboot import WineBoot

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class InstallerManager:

    def __init__(self, manager):
        self.__manager = manager
        self.__utils_conn = manager.utils_conn
        self.__component_manager = manager.component_manager
        self.__layer = None

    @lru_cache
    def get_review(self, installer_name):
        '''
        This function fetch the review for a given installer. It return
        the HTML formatted text if the review is found, else it will
        return an empty text.
        '''
        review = ""
        review_url = f"{BottlesRepositories.installers}Reviews/{installer_name}.md"

        try:
            with urllib.request.urlopen(review_url) as response:
                review = response.read().decode('utf-8')
                review = markdown.markdown(review)
        except:
            logging.error(f"Cannot fetch review for {installer_name}.")

        return review

    @lru_cache
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
                manifest_url = "%s/%s/%s.yml" % (
                    BottlesRepositories.installers,
                    installer_category,
                    installer_name
                )
                with urllib.request.urlopen(manifest_url) as url:
                    if plain:
                        '''
                        Caller required the component manifest
                        as plain text.
                        '''
                        return url.read().decode("utf-8")

                    # return as dictionary
                    return yaml.safe_load(url.read())
            except Exception as e:
                logging.error(f"Cannot fetch manifest for {installer_name}.")
                print(e)
                return False

        return False

    def __download_icon(self, config, executable: dict, manifest):
        icon_url = "%s/data/%s/%s" % (
            BottlesRepositories.installers,
            manifest.get('Name'),
            executable.get('icon')
        )
        bottle_icons_path = f"{ManagerUtils.get_bottle_path(config)}/icons"
        icon_path = f"{bottle_icons_path}/{executable.get('icon')}"

        if not os.path.exists(bottle_icons_path):
            os.makedirs(bottle_icons_path)
        if not os.path.isfile(icon_path):
            urllib.request.urlretrieve(icon_url, icon_path)

    def __install_dependencies(
        self,
        config,
        dependencies: list,
        widget: Gtk.Widget
    ):
        _config = config
        wineboot = WineBoot(_config)

        for dep in dependencies:
            widget.next_step()

            if dep in config.get("Installed_Dependencies"):
                continue

            _dep = [dep, self.__manager.supported_dependencies.get(dep)]
            
            if config.get("Environment") == "Layered":
                if LayersStore.get_layer_by_name(dep):
                    continue
                logging.info(f"Installing {dep} in a new layer.")
                layer = Layer().new(dep, self.__manager.get_latest_runner())
                layer.mount_bottle(config)
                _config = layer.runtime_conf
                wineboot.init()

            res = self.__manager.dependency_manager.install(_config, _dep)

            if config.get("Environment") == "Layered":
                layer.sweep()
                layer.save()

            if res.status == False:
                return False
        
        return True

    def __perform_steps(self, config, steps: list):
        for st in steps:
            # Step type: run_script
            if st.get("action") == "run_script":
                self.__step_run_script(config, st)
                
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

                    Runner.run_executable(
                        config=config,
                        file_path=f"{Paths.temp}/{file}",
                        arguments=st.get("arguments"),
                        environment=st.get("environment"),
                        no_async=True
                    )
    
    def __step_run_script(self, config, step: dict):
        placeholders = {
            "!bottle_path": ManagerUtils.get_bottle_path(config),
            "!bottle_drive": f"{ManagerUtils.get_bottle_path(config)}/drive_c",
            "!bottle_name": config.get("Name"),
            "!bottle_arch": config.get("Arch")
        }
        preventions = {
            "bottle.yml": "Bottle configuration cannot be modified."
        }
        script = step.get("script")

        for key, value in placeholders.items():
            script = script.replace(key, value)
        
        for key, value in preventions.items():
            if script.find(key) != -1:
                logging.error(value)
                return False

        res = subprocess.Popen(
            f"bash -c '{script}'",
            shell=True,
            cwd=ManagerUtils.get_bottle_path(config),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = res.communicate()
        logging.info(f"Executing installer script..")
        print(stdout.decode('utf-8'))
        logging.info(f"Finished executing installer script.")

    def __set_parameters(self, config, parameters: dict):
        _config = config
        _components_layers = []
        wineboot = WineBoot(_config)

        if parameters.get("dxvk") and not config.get("Parameters")["dxvk"]:
            if config["Environment"] == "Layered":
                if LayersStore.get_layer_by_name("dxvk"):
                    return
                logging.info(f"Installing DXVK in a new layer.")
                layer = Layer().new("dxvk", self.__manager.get_latest_runner())
                layer.mount_bottle(config)
                _components_layers.append(layer)
                _config = layer.runtime_conf
                wineboot.init()

            self.__manager.install_dll_component(_config, "dxvk")

        if parameters.get("vkd3d") and not config.get("Parameters")["vkd3d"]:
            if config["Environment"] == "Layered":
                if LayersStore.get_layer_by_name("vkd3d"):
                    return
                logging.info(f"Installing VKD3D in a new layer.")
                layer = Layer().new("vkd3d", self.__manager.get_latest_runner())
                layer.mount_bottle(config)
                _components_layers.append(layer)
                _config = layer.runtime_conf
                wineboot.init()

            self.__manager.install_dll_component(_config, "vkd3d")
        
        if parameters.get("dxvk_nvapi") and not config.get("Parameters")["dxvk_nvapi"]:
            if config["Environment"] == "Layered":
                if LayersStore.get_layer_by_name("dxvk_nvapi"):
                    return
                logging.info(f"Installing DXVK NVAPI in a new layer.")
                layer = Layer().new("dxvk_nvapi", self.__manager.get_latest_runner())
                layer.mount_bottle(config)
                _components_layers.append(layer)
                _config = layer.runtime_conf
                wineboot.init()

            self.__manager.install_dll_component(_config, "nvapi")
        
        # sweep and save layers
        for c in _components_layers:
            c.sweep()
            c.save()

        for param in parameters:
            self.__manager.update_config(
                config=config,
                key=param,
                value=parameters[param],
                scope="Parameters"
            )

    def __set_executable_arguments(self, config, executable: dict):
        '''
        TODO: Change config["Programs"] struct like External_Programs
        '''
        self.__manager.update_config(
            config=config,
            key=executable.get("file"),
            value=executable.get("arguments"),
            scope="Programs"
        )

    def __create_desktop_entry(self, config, manifest, executable: dict):
        bottle_icons_path = f"{ManagerUtils.get_bottle_path(config)}/icons"

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

    def count_steps(self, installer):
        manifest = self.get_installer(
            installer_name=installer[0],
            installer_category=installer[1]["Category"]
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
        
        return steps

    def install(self, config, installer, widget):
        if config.get("Environment") == "Layered":
            wineboot = WineBoot(self.__layer.runtime_conf)
            self.__layer = Layer().new(installer[0], self.__manager.get_latest_runner())
            self.__layer.mount_bottle(config)
            wineboot.init()

        manifest = self.get_installer(
            installer_name=installer[0],
            installer_category=installer[1]["Category"]
        )
        _config = config

        dependencies = manifest.get("Dependencies")
        parameters = manifest.get("Parameters")
        executable = manifest.get("Executable")
        steps = manifest.get("Steps")

        # download icon
        if executable.get("icon"):
            self.__download_icon(_config, executable, manifest)

        # install dependencies
        if dependencies:
            self.__install_dependencies(_config, dependencies, widget)

        # execute steps
        if steps:
            widget.next_step()
            if self.__layer is not None:
                for d in dependencies:
                    self.__layer.mount(name=d)
                self.__perform_steps(self.__layer.runtime_conf, steps)
            else:
                self.__perform_steps(_config, steps)

        # set parameters
        if parameters:
            widget.next_step()
            self.__set_parameters(_config, parameters)

        # register executable arguments
        if executable.get("arguments"):
            self.__set_executable_arguments(_config, executable)

        # create Desktop entry
        widget.next_step()
        self.__create_desktop_entry(_config, manifest, executable)

        if self.__layer is not None:
            # sweep and save
            self.__layer.sweep()
            self.__layer.save()
            
            # register layer
            _layer_launcher = {
                "uuid": self.__layer.get_uuid(),
                "name": manifest["Name"],
                "icon": "com.usebottles.bottles-program",
                "exec_path": f'{executable["path"]}/{executable["file"]}',
                "exec_name": executable["file"],
                "exec_args": executable["arguments"],
                "exec_env": {},
                "exec_cwd": executable["path"],
                "parameters": parameters,
                "mounts": dependencies,
            }
            self.__manager.update_config(
                config=config,
                key=self.__layer.get_uuid(),
                value=_layer_launcher,
                scope="Layers"
            )

        # unlock widget
        if widget is not None:
            GLib.idle_add(widget.set_installed)
