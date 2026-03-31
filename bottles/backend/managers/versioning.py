# versioning.py
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
from datetime import datetime
from gettext import gettext as _
from glob import glob
from typing import Any

from bottles.fvs.exceptions import (
    FVSNothingToCommit,
    FVSNothingToRestore,
    FVSStateNotFound,
    FVSStateZeroNotDeletable,
)
from bottles.fvs.repo import FVSRepo

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import Task, TaskManager
from bottles.backend.utils import yaml
from bottles.backend.utils.file import FileUtils
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


# noinspection PyTypeChecker
class VersioningManager:
    def __init__(self, manager):
        self.manager = manager

    @staticmethod
    def __get_patterns(config: BottleConfig):
        patterns = ["*dosdevices*", "*cache*"]
        if config.Parameters.versioning_exclusion_patterns:
            patterns += config.Versioning_Exclusion_Patterns
        return patterns

    @staticmethod
    def is_initialized(config: BottleConfig):
        bottle_path = ManagerUtils.get_bottle_path(config)
        # Check for FVS2
        if os.path.exists(os.path.join(bottle_path, ".fvs2")):
            return True
        return False

    @staticmethod
    def needs_migration(config: BottleConfig):
        """
        Check if the bottle uses a legacy versioning system.
        Legacy systems are identified by the presence of:
        - .fvs/ folder (FVS v1)
        - states/states.yml (internal legacy system)
        """
        bottle_path = ManagerUtils.get_bottle_path(config)
        
        # Check for FVS v1
        if os.path.exists(os.path.join(bottle_path, ".fvs")):
            return True
            
        # Check for absolute legacy (internal)
        if os.path.exists(os.path.join(bottle_path, "states", "states.yml")):
            return True
            
        # Fallback to config flag if any (and FVS2 is NOT there yet)
        if config.Versioning and not os.path.exists(os.path.join(bottle_path, ".fvs2")):
            return True
            
        return False

    @staticmethod
    def re_initialize(config: BottleConfig):
        bottle_path = ManagerUtils.get_bottle_path(config)
        
        # Clean up FVS v1
        fvs_path = os.path.join(bottle_path, ".fvs")
        if os.path.exists(fvs_path):
            shutil.rmtree(fvs_path)
            
        # Clean up absolute legacy
        states_path = os.path.join(bottle_path, "states")
        if os.path.exists(states_path):
            shutil.rmtree(states_path)
            
        # Clean up FVS2 for a fresh start
        fvs2_path = os.path.join(bottle_path, ".fvs2")
        if os.path.exists(fvs2_path):
            shutil.rmtree(fvs2_path)

    def update_system(self, config: BottleConfig):
        self.re_initialize(config)
        return self.manager.update_config(config, "Versioning", False)

    def create_state(self, config: BottleConfig, message: str = "No message"):
        patterns = self.__get_patterns(config)
        repo = FVSRepo(
            repo_path=ManagerUtils.get_bottle_path(config),
            use_compression=config.Parameters.versioning_compression,
        )
        task_id = TaskManager.add(Task(title=_("Committing state …")))
        try:
            repo.commit(message, ignore=patterns)
        except FVSNothingToCommit:
            TaskManager.remove(task_id)
            return Result(status=False, message=_("Nothing to commit"))

        repo._refresh()
        TaskManager.remove(task_id)
        return Result(
            status=True,
            message=_("New state [{0}] created successfully!").format(
                repo.active_state_id
            ),
            data={"state_id": repo.active_state_id, "states": repo.states, "branches": repo.branches, "active_branch": repo.active_branch},
        )

    def list_states(
        self, config: BottleConfig, check_dirty: bool = False
    ) -> dict[str, Any] | Result[dict[str, Any]]:
        """
        This function take all the states from the states.yml file
        of the given bottle and return them as a dict.
        """
        if not self.needs_migration(config):
            try:
                repo = FVSRepo(
                    repo_path=ManagerUtils.get_bottle_path(config),
                    use_compression=config.Parameters.versioning_compression,
                )
                if check_dirty:
                    repo.check_dirty()
            except FVSStateNotFound:
                logging.warning(
                    "The FVS repository may be corrupted, trying to re-initialize it"
                )
                self.re_initialize(config)
                repo = FVSRepo(
                    repo_path=ManagerUtils.get_bottle_path(config),
                    use_compression=config.Parameters.versioning_compression,
                )
                if check_dirty:
                    repo.check_dirty()
            return Result(
                status=True,
                message=_("States list retrieved successfully!"),
                data={"state_id": repo.active_state_id, "states": repo.states, "branches": repo.branches, "active_branch": repo.active_branch, "dirty": repo.dirty, "changed_files": repo.changed_files},
            )

        bottle_path = ManagerUtils.get_bottle_path(config)
        states = {}

        try:
            states_file = open("%s/states/states.yml" % bottle_path)
            states_file_yaml = yaml.load(states_file)
            states_file.close()
            if states_file_yaml:
                states = states_file_yaml.get("States", {})
                logging.info(f"Found [{len(states)}] states for bottle: [{config.Name}]")
            else:
                logging.info(f"No states found for bottle: [{config.Name}]")
        except (FileNotFoundError, yaml.YAMLError, AttributeError):
            logging.info(f"No states found for bottle: [{config.Name}]")

        return states

    def set_state(
        self, config: BottleConfig, state_id: str | int, after: callable = None
    ) -> Result:
        if not self.needs_migration(config):
            patterns = self.__get_patterns(config)
            repo = FVSRepo(
                repo_path=ManagerUtils.get_bottle_path(config),
                use_compression=config.Parameters.versioning_compression,
            )
            res = Result(
                status=True,
                message=_("State {0} restored successfully!").format(state_id),
            )
            task_id = TaskManager.add(
                Task(title=_("Restoring state {} …".format(state_id)))
            )
            try:
                repo.restore_state(state_id, ignore=patterns)
            except FVSStateNotFound:
                logging.error(f"State {state_id} not found.")
                res = Result(status=False, message=_("State not found"))
            except (FVSNothingToRestore, FVSStateZeroNotDeletable, FVSNothingToCommit): # Added FVSNothingToCommit just in case
                logging.error(f"State {state_id} is the active state.")
                res = Result(
                    status=False,
                    message=_("State {} is already the active state").format(state_id),
                )
            TaskManager.remove(task_id)
            return res

        bottle_path = ManagerUtils.get_bottle_path(config)
        logging.info(f"Restoring to state: [{state_id}]")

        # get bottle and state indexes
        bottle_index = self.get_index(config)
        state_index = self.get_state_files(config, state_id)

        search_sources = list(range(int(state_id) + 1))
        search_sources.reverse()

        # Optimize comparison using dicts for O(1) lookup
        bottle_files = {f["file"]: f for f in bottle_index.get("Files", [])}
        state_files = {f["file"]: f for f in state_index.get("Files", [])}

        remove_files = []
        edit_files = []
        for name, file in bottle_files.items():
            if name not in state_files:
                remove_files.append(file)
            elif file["checksum"] != state_files[name]["checksum"]:
                edit_files.append(file)

        add_files = []
        for name, file in state_files.items():
            if name not in bottle_files:
                add_files.append(file)

        logging.info(f"[{len(remove_files)}] files to remove.")
        logging.info(f"[{len(edit_files)}] files to replace.")
        logging.info(f"[{len(add_files)}] files to add.")

        # perform file updates
        for file in remove_files:
            file_path = "%s/drive_c/%s" % (bottle_path, file["file"])
            if os.path.exists(file_path):
                os.remove(file_path)

        for file in add_files:
            source = "%s/states/%s/drive_c/%s" % (
                bottle_path,
                str(state_id),
                file["file"],
            )
            target = "%s/drive_c/%s" % (bottle_path, file["file"])
            if os.path.exists(source):
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(source, target)

        for file in edit_files:
            target = "%s/drive_c/%s" % (bottle_path, file["file"])
            for i in search_sources:
                source = "%s/states/%s/drive_c/%s" % (bottle_path, str(i), file["file"])
                if os.path.isfile(source):
                    checksum = FileUtils().get_checksum(source)
                    if file["checksum"] == checksum:
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        shutil.copy2(source, target)
                        break

        # update State in bottle config
        self.manager.update_config(config, "State", state_id)

        # execute caller function after all
        if after:
            after()

        return Result(True)

    @staticmethod
    def get_state_files(
        config: BottleConfig, state_id: int, plain: bool = False
    ) -> str | Any:
        """
        Return the files.yml content of the state. Use the plain argument
        to return the content as plain text.
        """
        try:
            file = open(
                "%s/states/%s/files.yml"
                % (ManagerUtils.get_bottle_path(config), state_id)
            )
            files = file.read() if plain else yaml.load(file.read())
            file.close()
            return files
        except (OSError, IOError, yaml.YAMLError):
            logging.error("Could not read the state files file.")
            return {}

    @staticmethod
    def get_index(config: BottleConfig):
        """List all files in a bottle and return as dict."""
        bottle_path = ManagerUtils.get_bottle_path(config)
        cur_index = {"Update_Date": str(datetime.now()), "Files": []}
        for file in glob("%s/drive_c/**" % bottle_path, recursive=True):
            if not os.path.isfile(file):
                continue

            if os.path.islink(os.path.dirname(file)):
                continue

            if file[len(bottle_path) + 9 :].split("/")[0] in ["users"]:
                continue

            cur_index["Files"].append(
                {
                    "file": file[len(bottle_path) + 9 :],
                    "checksum": FileUtils().get_checksum(file),
                }
            )
        return cur_index

    def get_branches(self, config: BottleConfig) -> list:
        try:
            repo = FVSRepo(
                repo_path=ManagerUtils.get_bottle_path(config),
                use_compression=config.Parameters.versioning_compression,
            )
            return repo.branches
        except Exception as e:
            logging.error(f"Failed to get FVS branches: {e}")
            return []

    def get_active_branch(self, config: BottleConfig) -> str:
        try:
            repo = FVSRepo(
                repo_path=ManagerUtils.get_bottle_path(config),
                use_compression=config.Parameters.versioning_compression,
            )
            return repo.active_branch
        except Exception as e:
            logging.error(f"Failed to get active FVS branch: {e}")
            return ""

    def create_branch(self, config: BottleConfig, branch_name: str) -> Result:
        try:
            repo = FVSRepo(
                repo_path=ManagerUtils.get_bottle_path(config),
                use_compression=config.Parameters.versioning_compression,
            )
            repo.create_branch(branch_name)
            return Result(status=True, message=_("Branch created successfully"))
        except Exception as e:
            logging.error(f"Failed to create FVS branch: {e}")
            return Result(status=False, message=str(e))

    def delete_branch(self, config: BottleConfig, branch_name: str) -> Result:
        try:
            repo = FVSRepo(
                repo_path=ManagerUtils.get_bottle_path(config),
                use_compression=config.Parameters.versioning_compression,
            )
            repo.delete_branch(branch_name)
            return Result(status=True, message=_("Branch deleted successfully"))
        except Exception as e:
            logging.error(f"Failed to delete FVS branch: {e}")
            return Result(status=False, message=str(e))

    def checkout_branch(self, config: BottleConfig, branch_name: str) -> Result:
        try:
            patterns = self.__get_patterns(config)
            repo = FVSRepo(
                repo_path=ManagerUtils.get_bottle_path(config),
                use_compression=config.Parameters.versioning_compression,
            )

            try:
                repo.commit(
                    _("Auto-save before switching to %s") % branch_name,
                    ignore=patterns,
                )
            except FVSNothingToCommit:
                pass

            repo.checkout(branch_name)
            repo._refresh()

            if repo.active_state_id:
                repo.restore_state(repo.active_state_id, ignore=patterns)

            return Result(status=True)
        except Exception as e:
            logging.error(f"Failed to checkout FVS branch: {e}")
            return Result(status=False, message=str(e))
