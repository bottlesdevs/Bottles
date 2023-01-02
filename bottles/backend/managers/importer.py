# importer.py
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

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import yaml
import subprocess
from glob import glob
from datetime import datetime

from bottles.backend.logger import Logger
from bottles.backend.globals import TrdyPaths, Paths
from bottles.backend.models.result import Result

logging = Logger()


class ImportManager:

    def __init__(self, manager):
        self.manager = manager

    @staticmethod
    def search_wineprefixes() -> Result:
        """Look and return all 3rd party available wine prefixes"""
        importer_wineprefixes = []

        # search wine prefixes in external managers paths
        wine_standard = glob(TrdyPaths.wine)
        lutris_results = glob(f"{TrdyPaths.lutris}/*/")
        playonlinux_results = glob(f"{TrdyPaths.playonlinux}/*/")
        bottlesv1_results = glob(f"{TrdyPaths.bottlesv1}/*/")

        results = wine_standard + lutris_results + playonlinux_results + bottlesv1_results

        # count results
        is_wine = len(wine_standard)
        is_lutris = len(lutris_results)
        is_playonlinux = len(playonlinux_results)
        i = 1

        for wineprefix in results:
            wineprefix_name = wineprefix.split("/")[-2]

            # identify manager by index
            if i <= is_wine:
                wineprefix_manager = "Legacy Wine"
            elif i <= is_wine + is_lutris:
                wineprefix_manager = "Lutris"
            elif i <= is_wine + is_lutris + is_playonlinux:
                wineprefix_manager = "PlayOnLinux"
            else:
                wineprefix_manager = "Bottles v1"

            # check the drive_c path exists
            if os.path.isdir(os.path.join(wineprefix, "drive_c")):
                wineprefix_lock = os.path.isfile(os.path.join(wineprefix, "bottle.lock"))
                importer_wineprefixes.append(
                    {
                        "Name": wineprefix_name,
                        "Manager": wineprefix_manager,
                        "Path": wineprefix,
                        "Lock": wineprefix_lock
                    })
            i += 1

        logging.info(f"Found {len(importer_wineprefixes)} wine prefixes…")

        return Result(
            status=True,
            data={
                "wineprefixes": importer_wineprefixes
            }
        )

    def import_wineprefix(self, wineprefix: dict) -> Result:
        """Import wineprefix from external manager and convert in a bottle"""
        logging.info(f"Importing wineprefix {wineprefix['Name']} as bottle…")

        # prepare bottle path for the wine prefix
        bottle_path = f"Imported_{wineprefix.get('Name')}"
        bottle_complete_path = os.path.join(Paths.bottles, bottle_path)

        try:
            os.makedirs(bottle_complete_path, exist_ok=False)
        except (FileExistsError, OSError):
            logging.error(f"Error creating bottle directory for {wineprefix['Name']}")
            return Result(False)

        # create lockfile in source path
        logging.info(f"Creating lock file in {wineprefix['Path']}…")
        open(f'{wineprefix.get("Path")}/bottle.lock', 'a').close()

        # copy wineprefix files in the new bottle
        command = f"cp -a {wineprefix.get('Path')}/* {bottle_complete_path}/"
        subprocess.Popen(command, shell=True).communicate()

        # create bottle config
        new_config = BottleConfig()
        new_config.Name = wineprefix["Name"]
        new_config.Runner = self.manager.get_latest_runner()
        new_config.Path = bottle_path
        new_config.Environment = "Custom"
        new_config.Creation_Date = str(datetime.now())
        new_config.Update_Date = str(datetime.now())

        # save config
        saved = new_config.dump(os.path.join(bottle_complete_path, "bottle.yml"))
        if not saved.status:
            return Result(False)

        # update bottles view
        self.manager.update_bottles(silent=True)

        logging.info(f"Wine prefix {wineprefix['Name']} imported as bottle.", jn=True)
        return Result(True)
