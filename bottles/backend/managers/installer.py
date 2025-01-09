# installer_manager.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import os
import subprocess
import uuid
from functools import lru_cache
from typing import Optional

import markdown
import pycurl

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.managers.conf import ConfigManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.wine import WineUtils
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.winecommand import WineCommand

logging = Logger()


class InstallerManager:
    def __init__(self, manager, offline: bool = False):
        self.__manager = manager
        self.__repo = manager.repository_manager.get_repo("installers", offline)
        self.__utils_conn = manager.utils_conn
        self.__component_manager = manager.component_manager
        self.__local_resources = {}

    @lru_cache
    def get_review(self, installer_name, parse: bool = True) -> str:
        """Return an installer review from the repository (as HTML)"""
        review = self.__repo.get_review(installer_name)
        if not review:
            return "No review found for this installer."
        if parse:
            return markdown.markdown(review)
        return review

    @lru_cache
    def get_installer(
        self, installer_name: str, plain: bool = False
    ) -> str | dict | bool:
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

    def get_icon_url(self, installer):
        """Wrapper for the repo method."""
        return self.__repo.get_icon(installer)

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
                c = pycurl.Curl()
                c.setopt(c.URL, icon_url)
                c.setopt(c.WRITEDATA, open(icon_path, "wb"))
                c.perform()
                c.close()

    def __process_local_resources(self, exe_msi_steps, installer):
        files = self.has_local_resources(installer)
        if not files:
            return True
        for file in files:
            if file not in exe_msi_steps.keys():
                return False
            self.__local_resources[file] = exe_msi_steps[file]
        return True

    def __install_dependencies(
        self,
        config: BottleConfig,
        dependencies: list,
        step_fn: callable,
        is_final: bool = False,
    ):
        """Install a list of dependencies"""
        _config = config

        for dep in dependencies:
            if is_final:
                step_fn()

            if dep in config.Installed_Dependencies:
                continue

            _dep = [dep, self.__manager.supported_dependencies.get(dep)]
            res = self.__manager.dependency_manager.install(_config, _dep)

            if not res.ok:
                return False

        return True

    @staticmethod
    def __perform_checks(config, checks: dict):
        """Perform a list of checks"""
        bottle_path = ManagerUtils.get_bottle_path(config)

        if files := checks.get("files"):
            for f in files:
                if f.startswith("userdir/"):
                    current_user = os.getenv("USER")
                    f = f.replace("userdir/", f"users/{current_user}/")

                _f = os.path.join(bottle_path, "drive_c", f)
                if not os.path.exists(_f):
                    logging.error(
                        f"During checks, file {_f} was not found, assuming it is not installed. Aborting."
                    )
                    return False

        return True

    def __perform_steps(self, config: BottleConfig, steps: list):
        """Perform a list of actions"""
        for st in steps:
            # Step type: run_script
            if st.get("action") == "run_script":
                self.__step_run_script(config, st)

            # Step type: run_winecommand
            if st.get("action") == "run_winecommand":
                self.__step_run_winecommand(config, st)

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
                        checksum=st.get("file_checksum"),
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
                        environment=st.get("environment"),
                        monitoring=st.get("monitoring", []),
                    )
                    executor.run()
                else:
                    logging.error(
                        f"Failed to download {st.get('file_name')}, or checksum failed."
                    )
                    return False
        return True

    @staticmethod
    def __step_run_winecommand(config: BottleConfig, step: dict):
        """Run a wine command"""
        commands = step.get("commands")

        if not commands:
            return

        for command in commands:
            _winecommand = WineCommand(
                config,
                command=command.get("command"),
                arguments=command.get("arguments"),
                minimal=command.get("minimal"),
            )
            _winecommand.run()

    @staticmethod
    def __step_run_script(config: BottleConfig, step: dict):
        placeholders = {
            "!bottle_path": ManagerUtils.get_bottle_path(config),
            "!bottle_drive": f"{ManagerUtils.get_bottle_path(config)}/drive_c",
            "!bottle_name": config.Name,
            "!bottle_arch": config.Arch,
        }
        preventions = {"bottle.yml": "Bottle configuration cannot be modified."}
        script = step.get("script")

        for key, value in placeholders.items():
            script = script.replace(key, value)

        for key, value in preventions.items():
            if script.find(key) != -1:
                logging.error(
                    value,
                )
                return False

        logging.info("Executing installer script…")
        subprocess.Popen(
            f"bash -c '{script}'",
            shell=True,
            cwd=ManagerUtils.get_bottle_path(config),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).communicate()
        logging.info("Finished executing installer script.")

    @staticmethod
    def __step_update_config(config: BottleConfig, step: dict):
        bottle = ManagerUtils.get_bottle_path(config)
        conf_path = step.get("path")
        conf_type = step.get("type")
        del_keys = step.get("del_keys", {})
        upd_keys = step.get("upd_keys", {})

        if conf_path.startswith("userdir/"):
            current_user = os.getenv("USER")
            conf_path = conf_path.replace("userdir/", f"drive_c/users/{current_user}/")

        conf_path = f"{bottle}/{conf_path}"
        _conf = ConfigManager(config_file=conf_path, config_type=conf_type)

        for d in del_keys:
            _conf.del_key(d)

        _conf.merge_dict(upd_keys)

    def __set_parameters(self, config: BottleConfig, new_params: dict):
        _config = config

        if "dxvk" in new_params and isinstance(new_params["dxvk"], bool):
            if new_params["dxvk"] != config.Parameters.dxvk:
                self.__manager.install_dll_component(
                    _config, "dxvk", remove=not new_params["dxvk"]
                )

        if "vkd3d" in new_params and isinstance(new_params["vkd3d"], bool):
            if new_params["vkd3d"] != config.Parameters.vkd3d:
                self.__manager.install_dll_component(
                    _config, "vkd3d", remove=not new_params["vkd3d"]
                )

        if "dxvk_nvapi" in new_params and isinstance(new_params["dxvk_nvapi"], bool):
            if new_params["dxvk_nvapi"] != config.Parameters.dxvk_nvapi:
                self.__manager.install_dll_component(
                    _config, "nvapi", remove=not new_params["dxvk_nvapi"]
                )

        if "latencyflex" in new_params and isinstance(new_params["latencyflex"], bool):
            if new_params["latencyflex"] != config.Parameters.latencyflex:
                self.__manager.install_dll_component(
                    _config, "latencyflex", remove=not new_params["latencyflex"]
                )

        # avoid sync type change if not set to "wine"
        if "sync" in new_params and config.Parameters.sync != "wine":
            del new_params["sync"]

        for k, v in new_params.items():
            self.__manager.update_config(
                config=config, key=k, value=v, scope="Parameters"
            )

    def count_steps(self, installer) -> dict:
        manifest = self.get_installer(installer[0])
        steps = {"total": 0, "sections": []}
        if manifest.get("Dependencies"):
            i = int(len(manifest.get("Dependencies")))
            steps["sections"] += i * ["deps"]
            steps["total"] += i
        if manifest.get("Parameters"):
            steps["sections"].append("params")
            steps["total"] += 1
        if manifest.get("Steps"):
            i = int(len(manifest.get("Steps")))
            steps["sections"] += i * ["steps"]
            steps["total"] += i
        if manifest.get("Executable"):
            steps["sections"].append("exe")
            steps["total"] += 1
        if manifest.get("Checks"):
            steps["sections"].append("checks")
            steps["total"] += 1

        return steps

    def has_local_resources(self, installer):
        manifest = self.get_installer(installer[0])
        steps = manifest.get("Steps", [])
        exe_msi_steps = [
            s
            for s in steps
            if s.get("action", "") in ["install_exe", "install_msi"]
            and s.get("url", "") == "local"
        ]

        if len(exe_msi_steps) == 0:
            return []

        files = [s.get("file_name", "") for s in exe_msi_steps]
        return files

    def install(
        self,
        config: BottleConfig,
        installer: dict,
        step_fn: callable,
        is_final: bool = True,
        local_resources: Optional[dict] = None,
    ):
        manifest = self.get_installer(installer[0])
        _config = config

        bottle = ManagerUtils.get_bottle_path(config)
        installers = manifest.get("Installers")
        dependencies = manifest.get("Dependencies")
        parameters = manifest.get("Parameters")
        executable = manifest.get("Executable")
        steps = manifest.get("Steps")
        checks = manifest.get("Checks")

        # download icon
        if executable.get("icon"):
            self.__download_icon(_config, executable, manifest)

        # install dependent installers
        if installers:
            logging.info("Installing dependent installers")
            for i in installers:
                if not self.install(config, i, step_fn, False):
                    logging.error("Failed to install dependent installer(s)")
                    return Result(
                        False,
                        data={"message": "Failed to install dependent installer(s)"},
                    )

        # ask for local resources
        if local_resources:
            if not self.__process_local_resources(local_resources, installer):
                return Result(
                    False, data={"message": "Local resources not found or invalid"}
                )

        # install dependencies
        if dependencies:
            logging.info("Installing dependencies")
            if not self.__install_dependencies(
                _config, dependencies, step_fn, is_final
            ):
                return Result(
                    False, data={"message": "Dependencies installation failed."}
                )

        # set parameters
        if parameters:
            logging.info("Updating bottle parameters")
            if is_final:
                step_fn()

            self.__set_parameters(_config, parameters)

        # execute steps
        if steps:
            logging.info("Executing installer steps")
            if is_final:
                step_fn()

            if not self.__perform_steps(_config, steps):
                return Result(
                    False, data={"message": "Installer is not well configured."}
                )

        # execute checks
        if checks:
            logging.info("Executing installer checks")
            if is_final:
                step_fn()
                if not self.__perform_checks(_config, checks):
                    return Result(
                        False,
                        data={
                            "message": "Checks failed, the program is not installed."
                        },
                    )

        # register executable
        if executable["path"].startswith("userdir/"):
            _userdir = WineUtils.get_user_dir(bottle)
            executable["path"] = executable["path"].replace(
                "userdir/", f"/users/{_userdir}/"
            )

        _path = f'C:\\{executable["path"]}'.replace("/", "\\")
        _uuid = str(uuid.uuid4())
        _program = {
            "executable": executable["file"],
            "arguments": executable.get("arguments", ""),
            "name": executable["name"],
            "path": _path,
            "id": _uuid,
        }

        if "dxvk" in executable:
            _program["dxvk"] = executable["dxvk"]
        if "vkd3d" in executable:
            _program["vkd3d"] = executable["vkd3d"]
        if "dxvk_nvapi" in executable:
            _program["dxvk_nvapi"] = executable["dxvk_nvapi"]

        duplicates = [
            k for k, v in config.External_Programs.items() if v["path"] == _path
        ]
        ext = config.External_Programs

        if duplicates:
            for d in duplicates:
                del ext[d]
            ext[_uuid] = _program
            self.__manager.update_config(
                config=config, key="External_Programs", value=ext
            )
        else:
            self.__manager.update_config(
                config=config, key=_uuid, value=_program, scope="External_Programs"
            )

        # create Desktop entry
        bottles_icons_path = os.path.join(ManagerUtils.get_bottle_path(config), "icons")
        icon_path = os.path.join(bottles_icons_path, executable.get("icon"))
        ManagerUtils.create_desktop_entry(_config, _program, False, icon_path)

        if is_final:
            step_fn()

        logging.info(
            f"Program installed: {manifest['Name']} in {config.Name}.", jn=True
        )
        return Result(True)
