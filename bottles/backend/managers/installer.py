# installer_manager.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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
import glob
import os
import re
import subprocess
import threading
import uuid
from functools import lru_cache
from typing import Callable, Optional

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
from bottles.backend.wine.regkeys import RegKeys
from bottles.backend.wine.winecommand import WineCommand

logging = Logger()


class InstallerManager:
    def __init__(self, manager, offline: bool = False):
        self.__manager = manager
        self.__repo = manager.repository_manager.get_repo(
            "installers",
            offline,
            callback_in_main_loop=not manager.is_cli,
        )
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

    def refresh_catalog(self) -> dict:
        self.__repo.refresh()
        self.fetch_catalog.cache_clear()
        self.get_installer.cache_clear()
        self.get_review.cache_clear()
        return self.fetch_catalog()

    def get_icon_url(self, installer):
        """Wrapper for the repo method."""
        return self.__repo.get_icon(installer)

    @staticmethod
    def supports_channel(installer, include_unstable=False):
        channel = installer[1].get("Channel", "stable")
        return include_unstable or channel not in ("rc", "unstable")

    @staticmethod
    def supports_runner(installer, runner):
        runners = installer[1].get("Runners")
        if not runners:
            return True
        if not isinstance(runners, list):
            return False
        return any(
            isinstance(candidate, str)
            and (runner == candidate or runner.startswith(f"{candidate}-"))
            for candidate in runners
        )

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
                try:
                    with open(icon_path, "wb") as f:
                        c = pycurl.Curl()
                        _proxy = os.environ.get("http_proxy") or os.environ.get("https_proxy")
                        if _proxy:
                            c.setopt(pycurl.PROXY, _proxy)
                        c.setopt(c.URL, icon_url)
                        c.setopt(c.WRITEDATA, f)
                        c.perform()
                        c.close()
                except pycurl.error as e:
                    logging.error(f"Failed to download icon '{icon_url}': {e}")
                    if os.path.isfile(icon_path):
                        os.remove(icon_path)

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
                step_fn(dep)

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

    def __perform_steps(
        self,
        config: BottleConfig,
        steps: list,
        step_fn: Optional[Callable] = None,
        progress_fn: Optional[Callable[[Optional[float]], None]] = None,
        activity_fn: Optional[Callable[[Optional[str]], None]] = None,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        """Perform a list of actions"""
        for st in steps:
            if step_fn:
                step_fn()

            # Step type: run_script
            if st.get("action") == "run_script":
                if activity_fn:
                    activity_fn("installer script")
                if log_fn:
                    log_fn("Started installer script")
                result = self.__step_run_script(config, st, log_fn=log_fn)
                if not result.ok:
                    return result
                if log_fn:
                    log_fn("Finished installer script")
                if activity_fn:
                    activity_fn(None)

            # Step type: run_winecommand
            if st.get("action") == "run_winecommand":
                result = self.__step_run_winecommand(
                    config,
                    st,
                    progress_fn=progress_fn,
                    activity_fn=activity_fn,
                    log_fn=log_fn,
                )
                if not result.ok:
                    return result

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
                    file_name = os.path.basename(file_path)
                    if activity_fn:
                        activity_fn(file_name)
                    if log_fn:
                        log_fn(f"Started {file_name}")
                    result = executor.run()
                    if activity_fn:
                        activity_fn(None)
                    if not result.ok:
                        message = result.message or f"Failed to run {file_name}."
                        logging.error(message)
                        if log_fn:
                            log_fn(message)
                        return Result(False, message=message)
                    if log_fn:
                        log_fn(f"Finished {file_name}")
                else:
                    message = (
                        f"Failed to download {st.get('file_name')}, or checksum failed."
                    )
                    logging.error(message)
                    if log_fn:
                        log_fn(message)
                    return Result(False, message=message)
        return Result(True)

    @staticmethod
    def __progress_paths(config: BottleConfig, path: str) -> list[str]:
        if not isinstance(path, str) or not path:
            return []

        drive_c = os.path.realpath(
            os.path.join(ManagerUtils.get_bottle_path(config), "drive_c")
        )
        pattern = os.path.abspath(os.path.join(drive_c, path))

        try:
            if os.path.commonpath([drive_c, pattern]) != drive_c:
                return []
        except ValueError:
            return []

        paths = []
        for candidate in glob.glob(pattern):
            candidate = os.path.realpath(candidate)
            try:
                if os.path.commonpath([drive_c, candidate]) != drive_c:
                    continue
            except ValueError:
                continue
            if os.path.isfile(candidate):
                paths.append(candidate)
        return paths

    @classmethod
    def __progress_positions(
        cls, config: BottleConfig, progress: dict
    ) -> dict[str, int]:
        positions = {}
        encoding = progress.get("encoding", "utf-8")

        for path in cls.__progress_paths(config, progress.get("path", "")):
            try:
                with open(path, "r", encoding=encoding, errors="replace") as log:
                    log.seek(0, os.SEEK_END)
                    positions[path] = log.tell()
            except (LookupError, OSError):
                continue
        return positions

    @classmethod
    def __watch_progress(
        cls,
        config: BottleConfig,
        progress: dict,
        positions: dict[str, int],
        stop: threading.Event,
        progress_fn: Callable[[Optional[float]], None],
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        try:
            pattern = re.compile(progress.get("pattern", ""))
        except (re.error, TypeError):
            logging.error("Invalid installer progress pattern.")
            return

        maximum = progress.get("maximum", 100)
        encoding = progress.get("encoding", "utf-8")
        last_fraction = None
        final_pass = False

        while True:
            for path in cls.__progress_paths(config, progress.get("path", "")):
                try:
                    if os.path.getsize(path) < positions.get(path, 0):
                        positions[path] = 0

                    with open(path, "r", encoding=encoding, errors="replace") as log:
                        log.seek(positions.get(path, 0))
                        while True:
                            line_start = log.tell()
                            line = log.readline()
                            if not line:
                                break
                            if not line.endswith("\n"):
                                positions[path] = line_start
                                break
                            positions[path] = log.tell()

                            match = pattern.search(line)
                            if not match:
                                continue

                            if log_fn:
                                log_fn(line.strip()[:500])

                            try:
                                fraction = float(match.group(1)) / float(maximum)
                            except (
                                IndexError,
                                TypeError,
                                ValueError,
                                ZeroDivisionError,
                            ):
                                continue

                            fraction = max(0.0, min(1.0, fraction))
                            if fraction != last_fraction:
                                progress_fn(fraction)
                                last_fraction = fraction
                except (LookupError, OSError):
                    continue

            if final_pass:
                break
            final_pass = stop.wait(0.25)

    @classmethod
    def __step_run_winecommand(
        cls,
        config: BottleConfig,
        step: dict,
        progress_fn: Optional[Callable[[Optional[float]], None]] = None,
        activity_fn: Optional[Callable[[Optional[str]], None]] = None,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        """Run a wine command"""
        commands = step.get("commands")

        if not commands:
            return Result(True)

        for command in commands:
            skip_paths = command.get("skip_if_files_exist", [])
            if skip_paths:
                bottle = ManagerUtils.get_bottle_path(config)
                drive_c = os.path.realpath(os.path.join(bottle, "drive_c"))
                if all(
                    os.path.commonpath(
                        (drive_c, os.path.realpath(os.path.join(drive_c, path)))
                    )
                    == drive_c
                    and os.path.isfile(os.path.join(drive_c, path))
                    for path in skip_paths
                ):
                    continue

            command_name = os.path.basename(
                command.get("command", "").replace("\\", "/")
            )
            activity = command.get("label") or command_name
            if activity_fn:
                activity_fn(activity)
            if log_fn:
                log_fn(f"Started {command_name}")

            progress = command.get("progress")
            stop = None
            watcher = None
            if progress and progress_fn:
                progress_fn(None)
                positions = cls.__progress_positions(config, progress)
                stop = threading.Event()
                watcher = threading.Thread(
                    target=cls.__watch_progress,
                    args=(config, progress, positions, stop, progress_fn, log_fn),
                    daemon=True,
                )
                watcher.start()

            _winecommand = WineCommand(
                config,
                command=command.get("command"),
                arguments=command.get("arguments"),
                minimal=command.get("minimal"),
                communicate=command.get("wait", False),
            )
            try:
                result = _winecommand.run()
            finally:
                if stop:
                    stop.set()
                if watcher:
                    watcher.join()
                if progress_fn:
                    progress_fn(None)
                if activity_fn:
                    activity_fn(None)

            success_codes = command.get("success_codes", [])
            returncode = getattr(_winecommand, "returncode", None)
            if not result.ok and returncode not in success_codes:
                message = result.message or f"Failed to run {command_name}."
                logging.error(message)
                if log_fn:
                    if result.has_data:
                        for line in str(result.data).splitlines():
                            log_fn(line[:500])
                    log_fn(message)
                return Result(False, message=message)

            if result.has_data and log_fn:
                for line in str(result.data).splitlines():
                    log_fn(line[:500])
            if log_fn:
                log_fn(f"Finished {command_name}")

        return Result(True)

    @staticmethod
    def __step_run_script(
        config: BottleConfig,
        step: dict,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
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
                return Result(False, message=value)

        logging.info("Executing installer script…")
        process = subprocess.Popen(
            f"bash -c '{script}'",
            shell=True,
            cwd=ManagerUtils.get_bottle_path(config),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        if log_fn:
            for line in f"{stdout}\n{stderr}".splitlines():
                log_fn(line[:500])
        if process.returncode:
            message = f"Installer script exited with status {process.returncode}."
            logging.error(message)
            return Result(False, message=message)
        logging.info("Finished executing installer script.")
        return Result(True)

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

        if "decorated" in new_params and isinstance(new_params["decorated"], bool):
            RegKeys(config).set_decorated(new_params["decorated"])

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
        if manifest.get("Executable") or manifest.get("Executables"):
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
        progress_fn: Optional[Callable[[Optional[float]], None]] = None,
        activity_fn: Optional[Callable[[Optional[str]], None]] = None,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        manifest = self.get_installer(installer[0])
        _config = config

        installers = manifest.get("Installers")
        dependencies = manifest.get("Dependencies")
        parameters = manifest.get("Parameters")
        executable = manifest.get("Executable")
        executables = manifest.get("Executables")
        steps = manifest.get("Steps")
        checks = manifest.get("Checks")

        if executables is None:
            executables = [executable]
            skip_missing = False
        else:
            skip_missing = True

        if not isinstance(executables, list) or not executables or any(
            not isinstance(item, dict)
            or not item.get("file")
            or not item.get("name")
            for item in executables
        ):
            logging.error("Installer manifest has no valid executable block.")
            return Result(
                False,
                data={"message": "Installer is not well configured."},
            )

        for item in executables:
            if item.get("icon"):
                self.__download_icon(_config, item, manifest)

        # install dependent installers
        if installers:
            logging.info("Installing dependent installers")
            for i in installers:
                result = self.install(config, i, step_fn, False)
                if not result.ok:
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
            result = self.__perform_steps(
                _config,
                steps,
                step_fn=step_fn if is_final else None,
                progress_fn=progress_fn if is_final else None,
                activity_fn=activity_fn if is_final else None,
                log_fn=log_fn if is_final else None,
            )
            if not result.ok:
                message = result.message or "Installer step failed."
                return Result(
                    False,
                    data={"message": message},
                    message=message,
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

        registered = 0
        for item in executables:
            if self.__register_executable(_config, item, skip_missing):
                registered += 1

        if not registered:
            logging.error("No installer executable was found.")
            return Result(
                False,
                data={"message": "Checks failed, the program is not installed."},
            )

        if is_final:
            step_fn()

        logging.info(
            f"Program installed: {manifest['Name']} in {config.Name}.", jn=True
        )
        return Result(True)

    def __register_executable(self, config, executable, skip_missing=False):
        bottle = ManagerUtils.get_bottle_path(config)
        exec_path = executable.get("path", "")
        if exec_path.startswith("userdir/"):
            _userdir = WineUtils.get_user_dir(bottle)
            exec_path = exec_path.replace(
                "userdir/", f"/users/{_userdir}/"
            )

        if skip_missing:
            unix_path = os.path.join(bottle, "drive_c", exec_path.lstrip("/"))
            if not os.path.isfile(unix_path):
                return False

        _path = f"C:\\{exec_path}".replace("/", "\\")
        _uuid = str(uuid.uuid4())
        _program = {
            "executable": executable["file"],
            "arguments": executable.get("arguments", ""),
            "name": executable["name"],
            "path": _path,
            "id": _uuid,
        }

        optional_fields = (
            "d7vk",
            "dxvk",
            "vkd3d",
            "dxvk_nvapi",
            "gamescope",
            "virtual_desktop",
            "winebridge",
            "hide_console",
            "sync",
            "environment",
            "folder",
            "pre_script",
            "post_script",
            "pre_script_args",
            "post_script_args",
        )
        for field in optional_fields:
            if field in executable:
                _program[field] = executable[field]

        duplicates = [
            k for k, v in config.External_Programs.items() if v["path"] == _path
        ]
        ext = config.External_Programs

        if duplicates:
            for d in duplicates:
                file_extensions = ext[d].get("file_extensions")
                if file_extensions:
                    _program["file_extensions"] = file_extensions
                    break
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
        icon = executable.get("icon")
        icon_path = os.path.join(bottles_icons_path, icon) if icon else ""
        ManagerUtils.create_desktop_entry(config, _program, False, icon_path)

        return True
