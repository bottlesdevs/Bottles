# versioning.py
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

import os
import yaml
import uuid
import shutil
from glob import glob
from typing import NewType
from datetime import datetime
from gettext import gettext as _
from gi.repository import GLib

try:
    from bottles.operation import OperationManager  # pyright: reportMissingImports=false
except (RuntimeError, GLib.GError):
    from bottles.operation_cli import OperationManager

from bottles.backend.utils.file import FileUtils
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.logger import Logger

logging = Logger()


# noinspection PyTypeChecker
class VersioningManager:

    def __init__(self, window, manager):
        self.window = window
        self.manager = manager
        self.__operation_manager = OperationManager(self.window)

    def create_state(self, config: dict, comment: str = "No comment", update: bool = False):
        """
        Create a new bottle state. It will list all files in the bottle and
        compare them with the current index, looking for differences.
        """
        task_id = str(uuid.uuid4())
        logging.info(f"Creating new state for bottle: [{config['Name']}] …")

        bottle_path = ManagerUtils.get_bottle_path(config)
        GLib.idle_add(
            self.__operation_manager.new_task,
            task_id,
            _("Generating state files index …"),
            False
        )

        states_file_yaml = None

        # check if this is the first state
        first = True
        if os.path.isdir(f"{bottle_path}/states/"):
            first = False

        # get the current index (all files list)
        cur_index = self.get_index(config)

        if not first:
            '''
            If this is not the first state, we will compare the current
            index with the previous one. Otherwise, we will create a new
            state with the current index.
            '''
            states_file = open(f"{bottle_path}/states/states.yml")
            states_file_yaml = yaml.safe_load(states_file)
            states_file.close()

            state_index_file = open('%s/states/%s/index.yml' % (
                bottle_path,
                str(config.get("State")))
                                    )
            state_index = yaml.safe_load(state_index_file)
            state_index_file.close()
            state_index_files = state_index["Additions"] + state_index["Removed"] + state_index["Changes"]
            state_temp_checksums = [f["checksum"] for f in state_index_files]
            state_temp_files = [
                tuple([f["file"], f["checksum"]])
                for f in state_index_files
            ]
            cur_temp_files = [
                tuple([f["file"], f["checksum"]])
                for f in cur_index["Files"]
            ]
            additions = set(cur_temp_files) - set(state_temp_files)
            removed = set(state_temp_files) - set(cur_temp_files)

            new_state_index = {
                "Update_Date": str(datetime.now()),
                "Additions": [
                    {"file": f[0], "checksum": f[1]}
                    for f in additions
                ],
                "Removed": [
                    {"file": f[0], "checksum": f[1]}
                    for f in removed
                ],
                "Changes": [
                    {"file": f["file"], "checksum": f["checksum"]}
                    for f in cur_index["Files"]
                    if f["checksum"] not in state_temp_checksums
                ]
            }

            state_id = int(str(len(states_file_yaml.get("States"))))
        else:
            new_state_index = {
                "Update_Date": str(datetime.now()),
                "Additions": cur_index["Files"],
                "Removed": [],
                "Changes": []
            }
            state_id = 0

        state_path = "%s/states/%s" % (bottle_path, state_id)

        GLib.idle_add(self.__operation_manager.remove_task, task_id)
        GLib.idle_add(
            self.__operation_manager.new_task,
            task_id,
            _("Creating a restore point …"),
            False
        )

        try:
            '''
            Try to create the state folder and place the index.yml and
            files.yml files inside it. If it fails, it will return False.
            '''
            os.makedirs(
                f"{bottle_path}/states/{state_id}/drive_c",
                exist_ok=True
            )

            with open(f"{state_path}/index.yml", "w") as state_index_file:
                yaml.dump(new_state_index, state_index_file, indent=4)
                state_index_file.close()

            with open(f"{state_path}/files.yml", "w") as state_files_file:
                yaml.dump(cur_index, state_files_file, indent=4)
                state_files_file.close()
        except (OSError, IOError, yaml.YAMLError):
            return Result(
                status=False,
                message=_("Could not create the state folder.")
            )

        GLib.idle_add(self.__operation_manager.remove_task, task_id)
        GLib.idle_add(
            self.__operation_manager.new_task,
            task_id,
            _("Updating index …"),
            False
        )

        for file in cur_index["Files"]:
            '''
            For each file in the current index, we will copy it to the
            new state path.
            '''
            os.makedirs(
                "{0}/drive_c/{1}".format(
                    state_path,
                    "/".join(file["file"].split("/")[:-1])
                ),
                exist_ok=True
            )
            source = "{0}/drive_c/{1}".format(bottle_path, file["file"])
            target = "{0}/drive_c/{1}".format(state_path, file["file"])
            shutil.copy2(source, target)

        GLib.idle_add(self.__operation_manager.remove_task, task_id)
        GLib.idle_add(
            self.__operation_manager.new_task,
            task_id,
            _("Updating states …"),
            False
        )

        # update the states.yml file, appending the new state
        new_state = {
            "Creation_Date": str(datetime.now()),
            "Comment": comment
        }

        if not first:
            new_state_file = {
                "Update_Date": str(datetime.now()),
                "States": states_file_yaml.get("States")
            }
            new_state_file["States"][state_id] = new_state
        else:
            new_state_file = {
                "Update_Date": str(datetime.now()),
                "States": {0: new_state}
            }

        try:
            with open('%s/states/states.yml' % bottle_path, "w") as states_file:
                yaml.dump(new_state_file, states_file, indent=4)
                states_file.close()
        except (OSError, IOError, yaml.YAMLError):
            return Result(
                status=False,
                message=_("Could not update the states file.")
            )

        try:
            '''
            Try to create the new index.yml in the bottle's root folder.
            If it fails, it will return False.
            '''
            with open(f'{bottle_path}/states/index.yml', "w") as cur_index_file:
                yaml.dump(cur_index, cur_index_file, indent=4)
                cur_index_file.close()
        except (OSError, IOError, yaml.YAMLError):
            return Result(
                status=False,
                message=_("Could not update the index file.")
            )

        # update bottle configuration
        self.manager.update_config(config, "State", state_id)
        self.manager.update_config(config, "Versioning", True)

        logging.info(f"New state [{state_id}] created successfully!")

        if update:
            '''
            If the update flag is set, we will update the bottle's 
            states list.
            '''
            GLib.idle_add(
                self.window.page_details.view_versioning.update,
                False, config
            )

        # update the bottles' list
        self.manager.update_bottles()

        GLib.idle_add(self.__operation_manager.remove_task, task_id)

        return Result(
            status=True,
            message=_("New state [{0}] created successfully!").format(state_id),
            data={
                "state_id": state_id,
                "state_path": state_path,
                "states": self.list_states(config)
            }
        )

    @staticmethod
    def get_state_edits(
            config: dict,
            state_id: str,
            plain: bool = False
    ) -> dict:
        """
        Return the state index. Use the plain argument to return the
        index as plain text.
        """
        bottle_path = ManagerUtils.get_bottle_path(config)
        try:
            file = open('%s/states/%s/index.yml' % (bottle_path, state_id))
            content = file.read()
            files = yaml.safe_load(content)
            file.close()

            additions = len(files["Additions"])
            removed = len(files["Removed"])
            changes = len(files["Changes"])

            if plain:
                return {
                    "Plain": content,
                    "Additions": additions,
                    "Removed": removed,
                    "Changes": changes
                }

            return files
        except (OSError, IOError, yaml.YAMLError):
            logging.error(f"Could not read the state index file.")
            return {}

    @staticmethod
    def get_state_files(
            config: dict,
            state_id: int,
            plain: bool = False
    ) -> dict:
        """
        Return the files.yml content of the state. Use the plain argument
        to return the content as plain text.
        """
        bottle_path = ManagerUtils.get_bottle_path(config)

        try:
            file = open('%s/states/%s/files.yml' % (bottle_path, state_id))
            files = file.read() if plain else yaml.safe_load(file.read())
            file.close()
            return files
        except (OSError, IOError, yaml.YAMLError):
            logging.error(f"Could not read the state files file.")
            return {}

    @staticmethod
    def get_index(config: dict):
        """List all files in a bottle and return as dict."""
        bottle_path = ManagerUtils.get_bottle_path(config)
        cur_index = {
            "Update_Date": str(datetime.now()),
            "Files": []
        }
        for file in glob("%s/drive_c/**" % bottle_path, recursive=True):
            if not os.path.isfile(file):
                continue

            if os.path.islink(os.path.dirname(file)):
                continue

            if file[len(bottle_path) + 9:].split("/")[0] in ["users"]:
                continue

            cur_index["Files"].append({
                "file": file[len(bottle_path) + 9:],
                "checksum": FileUtils().get_checksum(file)
            })
        return cur_index

    def set_state(
            self,
            config: dict,
            state_id: int,
            after=False
    ) -> bool:
        """Restore a bottle to a state."""

        bottle_path = ManagerUtils.get_bottle_path(config)

        logging.info(f"Restoring to state: [{state_id}]")

        # get bottle and state indexes
        bottle_index = self.get_index(config)
        state_index = self.get_state_files(config, state_id)

        search_sources = list(range(int(state_id) + 1))
        search_sources.reverse()

        # check for removed and changed files
        remove_files = []
        edit_files = []
        for file in bottle_index.get("Files"):
            if file["file"] not in [file["file"] for file in state_index.get("Files")]:
                remove_files.append(file)
            elif file["checksum"] not in [file["checksum"] for file in state_index.get("Files")]:
                edit_files.append(file)
        logging.info(f"[{len(remove_files)}] files to remove.")
        logging.info(f"[{len(edit_files)}] files to replace.")

        # check for new files
        add_files = []
        for file in state_index.get("Files"):
            if file["file"] not in [file["file"] for file in bottle_index.get("Files")]:
                add_files.append(file)
        logging.info(f"[{len(add_files)}] files to add.")

        # perform file updates
        for file in remove_files:
            os.remove("%s/drive_c/%s" % (bottle_path, file["file"]))

        for file in add_files:
            for i in search_sources:
                source = "%s/states/%s/drive_c/%s" % (bottle_path, str(state_id), file["file"])
                target = "%s/drive_c/%s" % (bottle_path, file["file"])
                shutil.copy2(source, target)

        for file in edit_files:
            for i in search_sources:
                source = "%s/states/%s/drive_c/%s" % (
                    bottle_path, str(i), file["file"])
                if os.path.isfile(source):
                    checksum = FileUtils().get_checksum(source)
                    if file["checksum"] == checksum:
                        break
                target = "%s/drive_c/%s" % (bottle_path, file["file"])
                shutil.copy2(source, target)

        # update State in bottle config
        self.manager.update_config(config, "State", state_id)

        # update states
        GLib.idle_add(
            self.window.page_details.view_versioning.update,
            False, config
        )

        # update bottles
        self.manager.update_bottles()

        # execute caller function after all
        if after:
            GLib.idle_add(after)

        return True

    @staticmethod
    def list_states(config: dict) -> dict:
        """
        This function take all the states from the states.yml file
        of the given bottle and return them as a dict.
        """
        bottle_path = ManagerUtils.get_bottle_path(config)
        states = {}

        try:
            states_file = open('%s/states/states.yml' % bottle_path)
            states_file_yaml = yaml.safe_load(states_file)
            states_file.close()
            states = states_file_yaml.get("States")

            logging.info(f"Found [{len(states)}] states for bottle: [{config['Name']}]")
        except (FileNotFoundError, yaml.YAMLError):
            logging.info(f"No states found for bottle: [{config['Name']}]")

        return states
