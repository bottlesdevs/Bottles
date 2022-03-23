# component.py
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
import uuid
import shutil
import tarfile
import requests
from functools import lru_cache
from gi.repository import GLib
from typing import Union

from bottles.operation import OperationManager  # pyright: reportMissingImports=false
from bottles.backend.utils.generic import is_glibc_min_available
from bottles.backend.utils.file import FileUtils
from bottles.backend.globals import Paths
from bottles.backend.models.result import Result
from bottles.backend.downloader import Downloader
from bottles.backend.logger import Logger

from bottles.backend.managers.journal import JournalManager, JournalSeverity

logging = Logger()


class ComponentManager:

    def __init__(self, manager):
        self.__manager = manager
        self.__repo = manager.repository_manager.get_repo("components")
        self.__utils_conn = manager.utils_conn
        self.__window = manager.window
        self.__operation_manager = OperationManager(self.__window)

    @lru_cache
    def get_component(self, name: str, plain: bool = False) -> Union[str, dict, bool]:
        return self.__repo.get(name, plain)

    @lru_cache
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
                if "FLATPAK_ID" in os.environ and "-lol" in component[0].lower():
                    '''
                    Hide the lutris-lol runner if Bottles is running as 
                    Flatpak  because it is not compatible under sandbox
                    https://github.com/bottlesdevs/components/issues/54
                    '''
                    continue
                if "caffe" in component[0].lower():
                    if not is_glibc_min_available():
                        logging.warning(f"{component[0]} was found but it requires "
                                        "glibc >= 2.32 and your system is running an older "
                                        "version. Use the Flatpak instead if you can't "
                                        "upgrade your system. This runner will be ignored, "
                                        "please keep in mind that Bottles and all our "
                                        "installers are only tested with Caffe runners.", )
                        continue

                sub_category = component[1]["Sub-category"]
                catalog[sub_category][component[0]] = component[1]
                if component[0] in components_available[sub_category]:
                    catalog[sub_category][component[0]]["Installed"] = True

                continue

            category = component[1]["Category"]
            if category not in catalog:
                continue

            catalog[category][component[0]] = component[1]
            if component[0] in components_available[category]:
                catalog[category][component[0]]["Installed"] = True

        return catalog

    def download(
            self,
            download_url: str,
            file: str,
            rename: str = "",
            checksum: str = "",
            func=False
    ) -> bool:
        """Download a component from the Bottles repository."""

        # Check for missing Bottles paths before download
        self.__manager.check_app_dirs()

        '''
        Add new entry to the download manager and set the update_func
        to the task_entry update_status function by default.
        '''
        task_id = str(uuid.uuid4())
        GLib.idle_add(
            self.__operation_manager.new_task, task_id, file, False
        )

        _update_func = self.__operation_manager.update_task

        if download_url.startswith("temp/"):
            '''
            The caller is explicitly requesting a component from  
            the /temp directory. Nothing should be downloaded.
            '''
            return True

        if func:
            '''
            Set a function to be executing during the download. This 
            can be used to check the download status or update progress bars.
            '''
            _update_func = func

        def update_func(
                task_id,
                count=False,
                block_size=False,
                total_size=False,
                completed=False
        ):
            GLib.idle_add(_update_func, task_id, count, block_size, total_size, completed)

        existing_file = rename if rename else file
        just_downloaded = False

        if os.path.isfile(f"{Paths.temp}/{existing_file}"):
            '''
            Check if the file already exists in the /temp directory.
            If so, then skip the download process and set the update_func
            to completed.
            '''
            logging.warning(f"File [{existing_file}] already exists in temp, skipping.", )
            GLib.idle_add(update_func, task_id, False, False, False, True)
        else:
            '''
            As some urls can be redirect, we need to take care of this
            and make sure to use the final url. This check should be
            skipped for large files (e.g. runners).
            '''
            try:
                requests.packages.urllib3.disable_warnings()
                headers = {"User-Agent": "curl/7.79.1"}
                response = requests.head(
                    download_url,
                    allow_redirects=True,
                    headers=headers
                )
                download_url = response.url
                req_code = response.status_code
            except requests.exceptions.RequestException:
                GLib.idle_add(self.__operation_manager.remove_task, task_id)
                return False

            if req_code == 200:
                """
                If the status code is 200, the resource should be available
                and the download should be started. Any exceptions return
                False and the download is removed from the download manager.
                """
                res = Downloader(
                    url=download_url,
                    file=f"{Paths.temp}/{file}",
                    func=update_func
                ).download()

                if not res:
                    GLib.idle_add(self.__operation_manager.remove_task, task_id)
                    return False

                if not os.path.isfile(f"{Paths.temp}/{file}"):
                    """Fail if the file is not available in the /temp directory."""
                    GLib.idle_add(self.__operation_manager.remove_task, task_id)
                    return False

                just_downloaded = True
            else:
                GLib.idle_add(self.__operation_manager.remove_task, task_id)
                return False

        if rename and just_downloaded:
            """Renaming the downloaded file if requested."""
            logging.info(f"Renaming [{file}] to [{rename}].", )
            file_path = f"{Paths.temp}/{rename}"
            os.rename(f"{Paths.temp}/{file}", file_path)
        else:
            file_path = f"{Paths.temp}/{existing_file}"

        if checksum:
            """
            Compare the checksum of the downloaded file with the one
            provided by the caller. If they don't match, remove the
            file from the /temp directory, remove the entry from the
            download manager and return False.
            """
            checksum = checksum.lower()
            local_checksum = FileUtils().get_checksum(file_path)

            if local_checksum != checksum:
                logging.error(f"Downloaded file [{file}] looks corrupted.", )
                logging.error(f"Source cksum: [{checksum}] downloaded: [{local_checksum}]", )
                logging.info(f"Removing corrupted file [{file}].", )
                os.remove(file_path)
                GLib.idle_add(self.__operation_manager.remove_task, task_id)
                return False

        GLib.idle_add(self.__operation_manager.remove_task, task_id)
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
            logging.error(f"Unknown component [{component}].", )
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
            if component == "nvapi":
                '''
                TODO: this check should be make on archive root, so other
                components can benefit from it.
                '''
                xtr_path = f"{path}/{name}"
                tar.extractall(xtr_path)
            else:
                tar.extractall(path)
            tar.close()
        except:
            if os.path.isfile(os.path.join(Paths.temp, archive)):
                try:
                    os.remove(os.path.join(Paths.temp, archive))
                except:
                    pass  # safely ignore the error, there is nothing to remove

            if os.path.isdir(os.path.join(path, archive[:-7])):
                try:
                    shutil.rmtree(os.path.join(path, archive[:-7]))
                except:
                    pass  # safely ignore the error, there is nothing to remove

            logging.error("Extraction failed! Archive ends earlier than expected.", )
            return False

        if root_dir.endswith("x86_64"):
            try:
                '''
                If the folder ends with x86_64, remove this from its name.
                Return False if an folder with the same name already exists.
                '''
                shutil.move(
                    src=f"{path}/{root_dir}",
                    dst=f"{path}/{root_dir[:-7]}"
                )
            except (FileExistsError, shutil.Error):
                logging.error("Extraction failed! Component already exists.", )
                return False
        return True

    def install(
            self,
            component_type: str,
            component_name: str,
            func=False,
    ):
        """
        This function is used to install a component. It automatically
        gets the manifest from the given component and then calls the
        download and extract functions.
        """
        manifest = self.get_component(component_name)

        if not manifest:
            return Result(False)

        logging.info(f"Installing component: [{component_name}].", )

        # Download component
        download = self.download(
            download_url=manifest["File"][0]["url"],
            file=manifest["File"][0]["file_name"],
            rename=manifest["File"][0]["rename"],
            checksum=manifest["File"][0]["file_checksum"],
            func=func
        )

        if not download and func:
            '''
            If the download fails, execute the given func passing
            failed=True as a parameter.
            '''
            return func(failed=True)

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
            try:
                os.remove(os.path.join(Paths.temp, archive))
            except FileNotFoundError:
                pass  # safely ignore the error, there is nothing to remove

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
        JournalManager.write(
            severity=JournalSeverity.INFO,
            message=f"Component installed: {component_type} {component_name}"
        )

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
            logging.error(f"Unknown component type: {component_type}", )
            return

        if not os.path.isdir(os.path.join(path, dest)):
            shutil.move(
                src=os.path.join(path, source),
                dst=os.path.join(path, dest)
            )
