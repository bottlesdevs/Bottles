# importer.py
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

import os
import shutil
import subprocess
from datetime import datetime
from glob import glob

from bottles.backend.globals import Paths, TrdyPaths
from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result

logging = Logger()


class ImportManager:
    def __init__(self, manager):
        self.manager = manager

    @staticmethod
    def search_wineprefixes(selected_paths=None) -> Result:
        """Look and return all 3rd party available wine prefixes"""
        importer_wineprefixes = []

        # search wine prefixes in external managers paths
        results = [(path, "Legacy Wine") for path in glob(TrdyPaths.wine)]
        results += [(path, "Lutris") for path in glob(f"{TrdyPaths.lutris}/*/")]
        results += [
            (path, "PlayOnLinux") for path in glob(f"{TrdyPaths.playonlinux}/*/")
        ]
        results += [(path, "Bottles v1") for path in glob(f"{TrdyPaths.bottlesv1}/*/")]

        for selected_path in selected_paths or []:
            selected_path = os.path.normpath(selected_path)
            if os.path.isdir(os.path.join(selected_path, "drive_c")):
                results.append((selected_path, "Manual"))
            else:
                try:
                    with os.scandir(selected_path) as entries:
                        results += [
                            (entry.path, "Manual")
                            for entry in entries
                            if entry.is_dir()
                        ]
                except OSError:
                    pass

        seen = set()
        for wineprefix, wineprefix_manager in results:
            wineprefix = os.path.normpath(wineprefix)
            if wineprefix in seen:
                continue
            seen.add(wineprefix)
            wineprefix_name = os.path.basename(wineprefix)

            # check the drive_c path exists
            if os.path.isdir(os.path.join(wineprefix, "drive_c")):
                wineprefix_lock = os.path.isfile(
                    os.path.join(wineprefix, "bottle.lock")
                )
                importer_wineprefixes.append(
                    {
                        "Name": wineprefix_name,
                        "Manager": wineprefix_manager,
                        "Path": wineprefix,
                        "Lock": wineprefix_lock,
                    }
                )

        logging.info(f"Found {len(importer_wineprefixes)} wine prefixes…")

        return Result(status=True, data={"wineprefixes": importer_wineprefixes})

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

        # copy wineprefix files in the new bottle
        try:
            subprocess.run(
                [
                    "cp",
                    "-a",
                    os.path.join(wineprefix["Path"], "."),
                    bottle_complete_path,
                ],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            logging.error(f"Error copying wine prefix {wineprefix['Name']}: {error}")
            shutil.rmtree(bottle_complete_path, ignore_errors=True)
            return Result(False)

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
            shutil.rmtree(bottle_complete_path, ignore_errors=True)
            return Result(False)

        # mark the source as imported when it is writable
        try:
            with open(os.path.join(wineprefix["Path"], "bottle.lock"), "a"):
                pass
        except OSError as error:
            logging.warning(f"Could not mark the source prefix as imported: {error}")

        # update bottles view
        self.manager.update_bottles(silent=True)

        logging.info(f"Wine prefix {wineprefix['Name']} imported as bottle.", jn=True)
        return Result(True)
