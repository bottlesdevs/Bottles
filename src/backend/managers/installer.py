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
import markdown
import urllib.request
from typing import Union, NewType
from functools import lru_cache
from datetime import datetime
from gi.repository import Gtk, GLib

try:
    from bottles.operation import OperationManager  # pyright: reportMissingImports=false
except (RuntimeError, GLib.GError):
    from bottles.operation_cli import OperationManager

from bottles.dialogs.generic import MessageDialog

from bottles.backend.managers.conf import ConfigManager
from bottles.backend.managers.journal import JournalManager, JournalSeverity
from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.layers import LayersStore, Layer

from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.wine import WineUtils

from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.wine.executor import WineExecutor

logging = Logger()


class InstallerManager:

    def __init__(self, manager):
        self.__manager = manager
        self.__repo = manager.repository_manager.get_repo("installers")
        self.__utils_conn = manager.utils_conn
        self.__component_manager = manager.component_manager
        self.__layer = None
        self.__local_resources = {}

    @lru_cache
    def get_review(self, installer_name) -> str:
        """Return an installer review from the repository (as HTML)"""
        review = self.__repo.get_review(installer_name)
        if review:
            return markdown.markdown(review)
        return "No review found for this installer."

    @lru_cache
    def get_installer(
            self,
            installer_name: str,
            plain: bool = False
    ) -> Union[str, dict, bool]:
        """
        Return an installer manifest from the repository. Use the plain
        argument to get the manifest as plain text.
        """
        return self.__repo.get(installer_name, plain)

    @lru_cache
    def fetch_catalog(self) -> dict:
        """Fetch the installers catalog from the repository"""
        catalog = {}
        index = self.__repo.catalog
        if not self.__utils_conn.check_connection():
            return {}

        for installer in index.items():
            catalog[installer[0]] = installer[1]

        catalog = dict(sorted(catalog.items()))
        return catalog

    def __download_icon(self, config, executable: dict, manifest):
        """
        Download the installer icon from the repository to the bottle
        icons path.
        """
        icon_url = self.__repo.get_icon(manifest.get("Name"))
        bottle_icons_path = f"{ManagerUtils.get_bottle_path(config)}/icons"
        icon_path = f"{bottle_icons_path}/{executable.get('icon')}"

        if icon_url is not None:
            if not os.path.exists(bottle_icons_path):
                os.makedirs(bottle_icons_path)
            if not os.path.isfile(icon_path):
                urllib.request.urlretrieve(icon_url, icon_path)

    def __ask_for_local_resources(self, exe_msi_steps, _config):
        files = [s.get("file_name", "") for s in exe_msi_steps]

        # show confirmation dialog
        dialog = MessageDialog(
            parent=None,
            title=_("Installer requires local resources"),
            message=_(
                _("This installer requires some local resources: %s") % ", ".join(files)
            )
        )
        res = dialog.run()
        GLib.idle_add(dialog.destroy)
        if res != -5:
            return False

        for s in exe_msi_steps:
            _file_name = s.get("file_name")
            _ext = _file_name.split(".")[-1]
            _fd = Gtk.FileChooserNative.new(
                _("Pick executable for %s") % _file_name,
                None,
                Gtk.FileChooserAction.OPEN,
                _("Proceed"),
                _("Cancel")
            )
            _flt = Gtk.FileFilter()
            _flt.set_name(f".{_ext}")
            _flt.add_pattern(f"*.{_ext}")
            _fd.add_filter(_flt)
            _res = _fd.run()

            if _res == -3:
                self.__local_resources[_file_name] = _fd.get_filename()
            else:
                return False
        return True

    def __install_dependencies(
            self,
            config,
            dependencies: list,
            widget: Gtk.Widget
    ):
        """Install a list of dependencies"""
        _config = config
        wineboot = WineBoot(_config)

        for dep in dependencies:
            layer = None
            widget.next_step()

            if dep in config.get("Installed_Dependencies"):
                continue

            _dep = [dep, self.__manager.supported_dependencies.get(dep)]

            if config.get("Environment") == "Layered":
                if LayersStore.get_layer_by_name(dep):
                    continue
                logging.info(f"Installing {dep} in a new layer.", )
                layer = Layer().new(dep, self.__manager.get_latest_runner())
                layer.mount_bottle(config)
                _config = layer.runtime_conf
                wineboot.init()

            res = self.__manager.dependency_manager.install(_config, _dep)

            if config.get("Environment") == "Layered" and layer:
                layer.sweep()
                layer.save()

            if not res.status:
                return False

        return True

    def __perform_steps(self, config, steps: list):
        """Perform a list of actions"""
        for st in steps:
            # Step type: run_script
            if st.get("action") == "run_script":
                self.__step_run_script(config, st)

            # Step type: update_config
            if st.get("action") == "update_config":
                self.__step_update_config(config, st)

            # Step type: install_exe, install_msi
            if st["action"] in ["install_exe", "install_msi"]:
                if st["url"] != "local":
                    download = self.__component_manager.download(
                        st.get("url"),
                        st.get("file_name"),
                        st.get("rename"),
                        checksum=st.get("file_checksum")
                    )
                else:
                    download = True

                if download:
                    if st["url"] != "local":
                        if st.get("rename"):
                            file = st.get("rename")
                        else:
                            file = st.get("file_name")
                        file_path = f"{Paths.temp}/{file}"
                    else:
                        file_path = self.__local_resources[st.get("file_name")]

                    executor = WineExecutor(
                        config,
                        exec_path=file_path,
                        args=st.get("arguments"),
                        environment=st.get("environment")
                    )
                    executor.run()
                else:
                    _err = f"Failed to download {st.get('file_name')}, or checksum failed."
                    logging.error(_err)
                    JournalManager.write(severity=JournalSeverity.ERROR, message=_err)
                    return False
        return True

    @staticmethod
    def __step_run_script(config, step: dict):
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
                logging.error(value, )
                return False

        subprocess.Popen(
            f"bash -c '{script}'",
            shell=True,
            cwd=ManagerUtils.get_bottle_path(config),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        ).communicate()
        logging.info(f"Executing installer script..", )
        logging.info(f"Finished executing installer script.", )

    @staticmethod
    def __step_update_config(config, step: dict):
        bottle = ManagerUtils.get_bottle_path(config)
        conf_path = step.get("path")
        conf_type = step.get("type")
        del_keys = step.get("del_keys", {})
        upd_keys = step.get("upd_keys", {})

        if conf_path.startswith("userdir/"):
            current_user = os.getenv("USER")
            conf_path = conf_path.replace("userdir/", f"drive_c/users/{current_user}/")
        conf_path = f"{bottle}/{conf_path}"
        _conf = ConfigManager(conf_path, conf_type)

        for d in del_keys:
            _conf.del_key(d)

        _conf.merge_dict(upd_keys)

    def __set_parameters(self, config, parameters: dict):
        _config = config
        _components_layers = []
        wineboot = WineBoot(_config)

        if parameters.get("dxvk") and not config.get("Parameters")["dxvk"]:
            if config["Environment"] == "Layered":
                if LayersStore.get_layer_by_name("dxvk"):
                    return
                logging.info(f"Installing DXVK in a new layer.", )
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
                logging.info(f"Installing VKD3D in a new layer.", )
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
                logging.info(f"Installing DXVK NVAPI in a new layer.", )
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

        # avoid sync type change if not set to "wine"
        if parameters.get("sync") and config["Parameters"]["sync"] != "wine":
            del parameters["sync"]

        for param in parameters:
            self.__manager.update_config(
                config=config,
                key=param,
                value=parameters[param],
                scope="Parameters"
            )

    @staticmethod
    def __create_desktop_entry(config, manifest, executable: dict):
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

        try:
            # TODO: move to an util
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
        except (OSError, IOError) as e:
            logging.error(f"Failed to create desktop file. {e}")

    def count_steps(self, installer):
        manifest = self.get_installer(installer[0])
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
            self.__layer = Layer().new(installer[0], self.__manager.get_latest_runner())
            self.__layer.mount_bottle(config)
            wineboot = WineBoot(self.__layer.runtime_conf)
            wineboot.init()

        manifest = self.get_installer(installer[0])
        _config = config

        bottle = ManagerUtils.get_bottle_path(config)
        installers = manifest.get("Installers")
        dependencies = manifest.get("Dependencies")
        parameters = manifest.get("Parameters")
        executable = manifest.get("Executable")
        steps = manifest.get("Steps")

        # download icon
        if executable.get("icon"):
            self.__download_icon(_config, executable, manifest)

        # install dependent installers
        if installers:
            logging.info("Installing dependent installers")
            for i in installers:
                self.install(config, i, widget)

        # ask for local resources
        exe_msi_steps = [s for s in steps
                         if s.get("action", "") in ["install_exe", "install_msi"]
                         and s.get("url", "") == "local"]
        if exe_msi_steps:
            if not self.__ask_for_local_resources(exe_msi_steps, _config):
                # unlock widget
                if widget is not None:
                    GLib.idle_add(widget.set_err, _("Local resources not found or invalid"))
                return False

        # install dependencies
        if dependencies:
            logging.info("Installing dependencies")
            if not self.__install_dependencies(_config, dependencies, widget):
                # unlock widget
                if widget is not None:
                    GLib.idle_add(widget.set_err, _("Dependencies installation failed."))
                return False

        # set parameters
        if parameters:
            logging.info("Updating bottle parameters")
            widget.next_step()
            if self.__layer is not None:
                self.__set_parameters(self.__layer.runtime_conf, parameters)
            else:
                self.__set_parameters(_config, parameters)

        # execute steps
        if steps:
            logging.info("Executing installer steps")
            widget.next_step()
            if self.__layer is not None:
                for d in dependencies:
                    self.__layer.mount(name=d)
                wineboot = WineBoot(self.__layer.runtime_conf)
                wineboot.update()
                if not self.__perform_steps(self.__layer.runtime_conf, steps):
                    if widget is not None:  # unlock widget
                        GLib.idle_add(widget.set_err, _("Installation failed, please check the logs."))
                    return False
            else:
                if not self.__perform_steps(_config, steps):
                    if widget is not None:  # unlock widget
                        GLib.idle_add(widget.set_err, _("Installation failed, please check the logs."))
                    return False

        # register executable
        if self.__layer is None:
            if executable['path'].startswith("userdir/"):
                _userdir = WineUtils.get_user_dir(bottle)
                executable['path'] = executable['path'].replace(
                    "userdir/", f"/users/{_userdir}/"
                )
            _path = f'C:\\{executable["path"]}'.replace("/", "\\")
            _program = {
                "executable": executable["file"],
                "arguments": executable.get("arguments", ""),
                "name": executable["name"],
                "path": _path
            }
            self.__manager.update_config(
                config=config,
                key=executable["file"],
                value=_program,
                scope="External_Programs"
            )

        # create Desktop entry
        widget.next_step()
        self.__create_desktop_entry(_config, manifest, executable)

        if self.__layer is not None:
            # sweep and save
            self.__layer.sweep()
            self.__layer.save()
            _path = f'C:\\{executable["path"]}'.replace("/", "\\")

            # register layer
            _layer_launcher = {
                "uuid": self.__layer.get_uuid(),
                "name": manifest["Name"],
                "icon": "com.usebottles.bottles-program",
                "exec_path": _path,
                "exec_name": executable["file"],
                "exec_args": executable.get("arguments", ""),
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
