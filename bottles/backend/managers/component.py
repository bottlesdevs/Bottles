# component.py
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

import contextlib
import os
import shutil
import tarfile
from functools import lru_cache
from typing import Union, Optional

import pycurl

from bottles.backend.downloader import Downloader
from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.models.result import Result
from bottles.backend.state import State, Locks, Task, TaskStreamUpdateHandler, Status
from bottles.backend.utils.file import FileUtils
from bottles.backend.utils.generic import is_glibc_min_available
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


# noinspection PyTypeChecker
class ComponentManager:

    def __init__(self, manager, offline: bool = False, callback=None):
        self.__manager = manager
        self.__repo = manager.repository_manager.get_repo("components", offline, callback)
        self.__utils_conn = manager.utils_conn

    @lru_cache
    def get_component(self, name: str, plain: bool = False) -> Union[str, dict, bool]:
        return self.__repo.get(name, plain)

    def fetch_catalog(self) -> dict:
        """
        Fetch all components from the Bottles repository, mark the installed
        ones and return a dict with the catalog.
        """
        if not self.__utils_conn.check_connection():
            return {}

        catalog = {
            "runtimes": {},
            "wine": {},
            "proton": {},
            "dxvk": {},
            "vkd3d": {},
            "nvapi": {},
            "latencyflex": {},
            "winebridge": {}
        }
        components_available = {
            "runtimes": self.__manager.runtimes_available,
            "wine": self.__manager.runners_available,
            "proton": self.__manager.runners_available,
            "dxvk": self.__manager.dxvk_available,
            "vkd3d": self.__manager.vkd3d_available,
            "nvapi": self.__manager.nvapi_available,
            "latencyflex": self.__manager.latencyflex_available,
            "winebridge": self.__manager.winebridge_available
        }

        index = self.__repo.catalog

        for component in index.items():
            '''
            For each component, append it to the corresponding
            catalog and mark it as installed if it is.
            '''

            if component[1]["Category"] == "runners":
                if "soda" in component[0].lower() or "caffe" in component[0].lower():
                    if not is_glibc_min_available():
                        logging.warning(f"{component[0]} was found but it requires "
                                        "glibc >= 2.32 and your system is running an older "
                                        "version. Use the Flatpak instead if you can't "
                                        "upgrade your system. This runner will be ignored, "
                                        "please keep in mind that Bottles and all our "
                                        "installers are only tested with Soda and Caffe runners.")
                        continue

                sub_category = component[1]["Sub-category"]
                catalog[sub_category][component[0]] = component[1]
                if component[0] in components_available[sub_category]:
                    catalog[sub_category][component[0]]["Installed"] = True
                else:
                    catalog[sub_category][component[0]].pop("Installed", None)

                continue

            category = component[1]["Category"]
            if category not in catalog:
                continue

            catalog[category][component[0]] = component[1]
            if component[0] in components_available[category]:
                catalog[category][component[0]]["Installed"] = True
            else:
                catalog[category][component[0]].pop("Installed", None)

        return catalog

    def download(
            self,
            download_url: str,
            file: str,
            rename: str = "",
            checksum: str = "",
            func: Optional[TaskStreamUpdateHandler] = None
    ) -> bool:
        """Download a component from the Bottles repository."""

        # Check for missing Bottles paths before download
        self.__manager.check_app_dirs()

        # Register this file download task to TaskManager
        task = Task(title=file)
        task_id = State.add_task(task)
        update_func = task.stream_update if not func else func

        if download_url.startswith("temp/"):
            '''
            The caller is explicitly requesting a component from
            the /temp directory. Nothing should be downloaded.
            '''
            return True

        existing_file = rename if rename else file
        temp_dest = os.path.join(Paths.temp, file)
        just_downloaded = False

        if os.path.isfile(os.path.join(Paths.temp, existing_file)):
            '''
            Check if the file already exists in the /temp directory.
            If so, then skip the download process and set the update_func
            to completed.
            '''
            logging.warning(f"File [{existing_file}] already exists in temp, skipping.")
        else:
            '''
            As some urls can be redirect, we need to take care of this
            and make sure to use the final url. This check should be
            skipped for large files (e.g. runners).
            '''
            c = pycurl.Curl()
            try:
                c.setopt(c.URL, download_url)
                c.setopt(c.FOLLOWLOCATION, True)
                c.setopt(c.HTTPHEADER, ["User-Agent: curl/7.79.1"])
                c.setopt(c.NOBODY, True)
                c.perform()

                req_code = c.getinfo(c.RESPONSE_CODE)
                download_url = c.getinfo(c.EFFECTIVE_URL)
            except pycurl.error:
                logging.exception(f"Failed to download [{download_url}]")
                State.remove_task(task_id)
                return False
            finally:
                c.close()

            if req_code == 200:
                """
                If the status code is 200, the resource should be available
                and the download should be started. Any exceptions return
                False and the download is removed from the download manager.
                """
                res = Downloader(
                    url=download_url,
                    file=temp_dest,
                    update_func=update_func
                ).download()

                if not res.status:
                    State.remove_task(task_id)
                    return False

                if not os.path.isfile(temp_dest):
                    """Fail if the file is not available in the /temp directory."""
                    State.remove_task(task_id)
                    return False

                just_downloaded = True
            else:
                logging.warning(f"Failed to download [{download_url}] with code: {req_code} != 200")
                State.remove_task(task_id)
                return False

        file_path = os.path.join(Paths.temp, existing_file)
        if rename and just_downloaded:
            """Renaming the downloaded file if requested."""
            logging.info(f"Renaming [{file}] to [{rename}].")
            file_path = os.path.join(Paths.temp, rename)
            os.rename(temp_dest, file_path)

        if checksum:
            """
            Compare the checksum of the downloaded file with the one
            provided by the caller. If they don't match, remove the
            file from the /temp directory, remove the entry from the
            task manager and return False.
            """
            checksum = checksum.lower()
            local_checksum = FileUtils().get_checksum(file_path)

            if local_checksum and local_checksum != checksum:
                logging.error(f"Downloaded file [{file}] looks corrupted.")
                logging.error(f"Source cksum: [{checksum}] downloaded: [{local_checksum}]")
                logging.error(f"Removing corrupted file [{file}].")
                os.remove(file_path)
                State.remove_task(task_id)
                return False

        State.remove_task(task_id)
        return True

    @staticmethod
    def extract(name: str, component: str, archive: str) -> True:
        """Extract a component from an archive."""

        if component in ["runner", "runner:proton"]:
            path = Paths.runners
        elif component == "dxvk":
            path = Paths.dxvk
        elif component == "vkd3d":
            path = Paths.vkd3d
        elif component == "nvapi":
            path = Paths.nvapi
        elif component == "latencyflex":
            path = Paths.latencyflex
        elif component == "runtime":
            path = Paths.runtimes
        elif component == "winebridge":
            path = Paths.winebridge
        else:
            logging.error(f"Unknown component [{component}].")
            return False

        try:
            '''
            Try to extract the archive in the /temp directory.
            If the extraction fails, remove the archive from the /temp
            directory and return False. The common cause of a failed 
            extraction is that the archive is corrupted.
            '''
            tar = tarfile.open(f"{Paths.temp}/{archive}")
            root_dir = tar.getnames()[0]
            tar.extractall(path)
            tar.close()
        except (tarfile.TarError, IOError, EOFError):
            with contextlib.suppress(FileNotFoundError):
                os.remove(os.path.join(Paths.temp, archive))
            with contextlib.suppress(FileNotFoundError):
                shutil.rmtree(os.path.join(path, archive[:-7]))

            logging.error("Extraction failed! Archive ends earlier than expected.")
            return False

        if root_dir.endswith("x86_64"):
            try:
                '''
                If the folder ends with x86_64, remove this from its name.
                Return False if an folder with the same name already exists.
                '''
                root_dir = os.path.join(path, root_dir)
                shutil.move(
                    src=root_dir,
                    dst=root_dir[:-7]
                )
            except (FileExistsError, shutil.Error):
                logging.error("Extraction failed! Component already exists.")
                return False
        return True

    @State.lock(Locks.ComponentsInstall)  # avoid high resource usage
    def install(
            self,
            component_type: str,
            component_name: str,
            func: Optional[TaskStreamUpdateHandler] = None,
    ):
        """
        This function is used to install a component. It automatically
        gets the manifest from the given component and then calls the
        download and extract functions.
        """
        manifest = self.get_component(component_name)

        if not manifest:
            return Result(False)

        logging.info(f"Installing component: [{component_name}].")
        file = manifest["File"][0]

        res = self.download(
            download_url=file["url"],
            file=file["file_name"],
            rename=file["rename"],
            checksum=file["file_checksum"],
            func=func
        )

        if not res:
            '''
            If the download fails, execute the given func passing
            failed=True as a parameter.
            '''
            if func:
                func(status=Status.FAILED)
            return Result(False)

        archive = manifest["File"][0]["file_name"]

        if manifest["File"][0]["rename"]:
            '''
            If the component has a rename, rename the downloaded file
            to the required name.
            '''
            archive = manifest["File"][0]["rename"]

        self.extract(component_name, component_type, archive)

        '''
        Execute Post Install if the component has it defined
        in the manifest.
        '''
        if "Post" in manifest:
            print(f"Executing post install for [{component_name}].")

            for post in manifest.get("Post", []):
                if post["action"] == "rename":
                    self.__post_rename(component_type, post)

        '''
        Ask the manager to re-organize its components.
        Note: I know that this is not the most efficient way to do this,
        please give feedback if you know a better way to avoid this.
        '''
        if component_type in ["runtime", "winebridge"]:
            with contextlib.suppress(FileNotFoundError):
                os.remove(os.path.join(Paths.temp, archive))

        if component_type in ["runner", "runner:proton"]:
            self.__manager.check_runners()

        elif component_type == "dxvk":
            self.__manager.check_dxvk()

        elif component_type == "vkd3d":
            self.__manager.check_vkd3d()

        elif component_type == "nvapi":
            self.__manager.check_nvapi()

        elif component_type == "runtime":
            self.__manager.check_runtimes()

        elif component_type == "winebridge":
            self.__manager.check_winebridge()

        self.__manager.organize_components()
        logging.info(f"Component installed: {component_type} {component_name}", jn=True)

        return Result(True)

    @staticmethod
    def __post_rename(component_type: str, post: dict):
        source = post.get("source")
        dest = post.get("dest")

        if component_type in ["runner", "runner:proton"]:
            path = Paths.runners
        elif component_type == "dxvk":
            path = Paths.dxvk
        elif component_type == "vkd3d":
            path = Paths.vkd3d
        elif component_type == "nvapi":
            path = Paths.nvapi
        else:
            logging.error(f"Unknown component type: {component_type}")
            return

        if not os.path.isdir(os.path.join(path, dest)):
            shutil.move(
                src=os.path.join(path, source),
                dst=os.path.join(path, dest)
            )

    def is_in_use(self, component_type: str, component_name: str):
        bottles = self.__manager.local_bottles

        if component_type in ["runner", "runner:proton"]:
            return component_name in [b["Runner"] for _, b in bottles.items()]
        if component_type == "dxvk":
            return component_name in [b["DXVK"] for _, b in bottles.items()]
        if component_type == "vkd3d":
            return component_name in [b["VKD3D"] for _, b in bottles.items()]
        if component_type == "nvapi":
            return component_name in [b["NVAPI"] for _, b in bottles.items()]
        if component_type == "latencyflex":
            return component_name in [b["LatencyFleX"] for _, b in bottles.items()]
        if component_type in ["runtime", "winebridge"]:
            return True
        return False

    def uninstall(self, component_type: str, component_name: str):
        if self.is_in_use(component_type, component_name):
            return Result(False, data={"message": f"Component in use and cannot be removed: {component_name}"})

        if component_type in ["runner", "runner:proton"]:
            path = ManagerUtils.get_runner_path(component_name)

        elif component_type == "dxvk":
            path = ManagerUtils.get_dxvk_path(component_name)

        elif component_type == "vkd3d":
            path = ManagerUtils.get_vkd3d_path(component_name)

        elif component_type == "nvapi":
            path = ManagerUtils.get_nvapi_path(component_name)

        elif component_type == "latencyflex":
            path = ManagerUtils.get_latencyflex_path(component_name)

        else:
            logging.error(f"Unknown component type: {component_type}")
            return Result(False, data={"message": "Unknown component type."})

        if not os.path.isdir(path):
            return Result(False, data={"message": "Component not installed."})

        try:
            shutil.rmtree(path)
        except Exception as e:
            logging.error(f"Failed to uninstall component: {component_name}, {e}")
            return Result(False, data={"message": "Failed to uninstall component."})

        '''
        Ask the manager to re-organize its components.
        Note: I know that this is not the most efficient way to do this,
        please give feedback if you know a better way to avoid this.
        '''
        if component_type in ["runner", "runner:proton"]:
            self.__manager.check_runners()

        elif component_type == "dxvk":
            self.__manager.check_dxvk()

        elif component_type == "vkd3d":
            self.__manager.check_vkd3d()

        elif component_type == "nvapi":
            self.__manager.check_nvapi()

        elif component_type == "runtime":
            self.__manager.check_runtimes()

        elif component_type == "winebridge":
            self.__manager.check_winebridge()

        self.__manager.organize_components()
        logging.info(f"Component uninstalled: {component_type} {component_name}")

        return Result(True)
