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
import yaml
import time
import shutil
import tarfile
import requests
import urllib.request
from typing import NewType
from gi.repository import GLib

from ..download import DownloadManager
from .globals import Paths, BottlesRepositories
from ..utils import UtilsLogger, UtilsFiles

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)

logging = UtilsLogger()

class ComponentManager:

    def __init__(self, manager):
        self.__manager = manager
        self.__utils_conn = manager.utils_conn
        self.__window = manager.window
        self.__download_manager = DownloadManager(self.__window)
    
    def fetch_catalog(self) -> dict:
        '''
        This function fetch all components from the Bottles repository
        and mark the installed ones. Then return a dictionary with all
        the components, divided by type.
        '''
        if not self.__utils_conn.check_connection():
            return False
        
        catalog_wine = {}
        catalog_proton = {}
        catalog_dxvk = {}
        catalog_vkd3d = {}

        try:
            with urllib.request.urlopen(
                BottlesRepositories.components_index
            ) as req:
                index = yaml.safe_load(req.read())

            for component in index.items():
                '''
                For each component, append it to the corresponding
                catalog and mark it as installed if it is.
                '''

                if component[1]["Category"] == "runners":
                    if "FLATPAK_ID" in os.environ and "-lol" in component[0]:
                        '''
                        Hide the lutris-lol runner if Bottles is running as 
                        Flatpak  because it is not compatible under sandbox
                        https://github.com/bottlesdevs/components/issues/54
                        '''
                        continue

                    if component[1]["Sub-category"] == "wine":
                        catalog_wine[component[0]] = component[1]
                        if component[0] in self.__manager.runners_available:
                            catalog_wine[component[0]]["Installed"] = True

                    if component[1]["Sub-category"] == "proton":
                        catalog_proton[component[0]] = component[1]
                        if component[0] in self.__manager.runners_available:
                            catalog_proton[component[0]]["Installed"] = True

                if component[1]["Category"] == "dxvk":
                    catalog_dxvk[component[0]] = component[1]
                    if component[0] in self.__manager.dxvk_available:
                        catalog_dxvk[component[0]]["Installed"] = True

                if component[1]["Category"] == "vkd3d":
                    catalog_vkd3d[component[0]] = component[1]
                    if component[0] in self.__manager.vkd3d_available:
                        catalog_vkd3d[component[0]]["Installed"] = True
            req.close()

            return {
                "wine": catalog_wine,
                "proton": catalog_proton,
                "dxvk": catalog_dxvk,
                "vkd3d": catalog_vkd3d
            }
        except:
            logging.error(f"Cannot fetch components list.")
            return {}

    def download(
        self,
        component: str,
        download_url: str,
        file: str,
        rename: bool = False,
        checksum: bool = False,
        func=False
    ) -> bool:
        # Check for missing Bottles paths before download
        self.__manager.check_runners_dir()

        '''
        Add new entry to the download manager and set the update_func
        to the download_entry update_status function by default.
        '''
        download_entry = self.__download_manager.new_download(
            file_name=file, 
            cancellable=False
        )
        update_func = download_entry.update_status
        time.sleep(1)

        if download_url.startswith("temp/"):
            '''
            The caller is explicitly requesting a component from  
            the /temp directory. Nothing should be downloaded.
            '''
            return True

        if func:
            '''
            Set a function to be executing during the downlaod. This 
            can be used to check the download status or update progress bars.
            '''
            update_func = func

        existing_file = rename if rename else file
        just_downloaded = False

        if os.path.isfile(f"{Paths.temp}/{existing_file}"):
            '''
            Check if the file already exists in the /temp directory.
            If so, then skip the download process and set the update_func
            to completed.
            '''
            logging.warning(
                f"File [{existing_file}] already exists in temp, skipping."
            )
            GLib.idle_add(update_func, False, False, False, True)
        else:
            '''
            As some urls can be redirect, we need to take care of this
            and make sure to use the final url. This check should be
            skipped for large files (e.g. runners).
            '''
            if component not in ["runner", "runner:proton", "installer"]:
                download_url = requests.get(
                    url=download_url, 
                    allow_redirects=True
                ).url
            try:
                request = urllib.request.urlopen(download_url)
            except (urllib.error.HTTPError, urllib.error.URLError):
                GLib.idle_add(download_entry.remove)
                return False

            if request.status == 200:
                '''
                If the status code is 200, the resource should be available
                and the download should be started. Any exceptions return
                False and the download is removed from the download manager.
                '''
                try:
                    urllib.request.urlretrieve(
                        url= download_url,
                        filename=f"{Paths.temp}/{file}",
                        reporthook=update_func
                    )
                except:
                    GLib.idle_add(download_entry.remove)
                    return False

                just_downloaded = True
            else:
                GLib.idle_add(download_entry.remove)
                return False

        if rename and just_downloaded:
            # Rename the downloaded file if the caller asked for it.
            logging.info(f"Renaming [{file}] to [{rename}].")
            file_path = f"{Paths.temp}/{rename}"
            os.rename(f"{Paths.temp}/{file}", file_path)
        else:
            file_path = f"{Paths.temp}/{existing_file}"

        if checksum:
            '''
            Compare the checksum of the downloaded file with the one
            provided by the caller. If they don't match, remove the
            file from the /temp directory, remove the entry from the
            download manager and return False.
            '''
            checksum = checksum.lower()
            local_checksum = UtilsFiles().get_checksum(file_path)

            if local_checksum != checksum:
                logging.error(f"Downloaded file [{file}] looks corrupted.")
                logging.error(
                    f"Source cksum: [{checksum}] downloaded: [{local_checksum}]"
                )

                os.remove(file_path)
                GLib.idle_add(download_entry.remove)
                return False

        GLib.idle_add(download_entry.remove)
        return True

    def extract(self, component: str, archive: str) -> True:
        # Set the destination path according to the component type
        if component in ["runner", "runner:proton"]:
            path = Paths.runners
        if component == "dxvk":
            path = Paths.dxvk
        if component == "vkd3d":
            path = Paths.vkd3d

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
        except:
            if os.path.isfile(os.path.join(Paths.temp, archive)):
                os.remove(os.path.join(Paths.temp, archive))

            if os.path.isdir(os.path.join(path, archive[:-7])):
                shutil.rmtree(os.path.join(path, archive[:-7]))

            logging.error(
                "Extraction failed! Archive ends earlier than expected."
            )
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
            except:
                logging.error("Extraction failed! Component already exists.")
                return False
        return True

    def install(
        self, 
        component_type: str, 
        component_name: str, 
        after=False, 
        func=False, 
        checks=True
    ) -> None:
        return
