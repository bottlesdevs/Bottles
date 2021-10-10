import os
import yaml
import time
import shutil
from glob import glob
from typing import NewType
from datetime import datetime
from gettext import gettext as _

from ..operation import OperationManager
from ..utils import UtilsLogger, UtilsFiles, RunAsync
from .runner import Runner

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)


class RunnerVersioning:

    def __init__(self, window, manager):
        self.window = window
        self.manager = manager

    def async_create_bottle_state(self, args: list) -> bool:
        '''
        This function creates a new bottle state.
        It will list all files in the bottle and compare them with the
        current index, looking for differences. So it will create a new
        state with the differences and its index/files yaml files. If 
        this is the first state, it will create the states folder and
        the index file. It will return True if the state was created, 
        False otherwise.
        '''
        config, comment, update, no_update, after = args

        logging.info(
            f"Creating new state for bottle: [{config['Name']}] …"
        )

        bottle_path = Runner().get_bottle_path(config)
        self.operation_manager = OperationManager(self.window)
        task_entry = self.operation_manager.new_task(
            file_name=_("Generating state files index …"),
            cancellable=False
        )

        # check if this is the first state
        first = True
        if os.path.isdir(f"{bottle_path}/states/"):
            first = False

        # get the current index (all files list)
        cur_index = self.get_bottle_index(config)

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
            state_index_files = state_index["Additions"] +\
                state_index["Removed"] +\
                state_index["Changes"]

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
                "Additions": [],
                "Removed": [],
                "Changes": []
            }

            for file in additions:
                new_state_index["Additions"].append({
                    "file": file[0],
                    "checksum": file[1]
                })

            for file in removed:
                new_state_index["Removed"].append({
                    "file": file[0],
                    "checksum": file[1]
                })

            for file in cur_index["Files"]:
                if file["checksum"] not in state_temp_checksums:
                    new_state_index["Changes"].append({
                        "file": file["file"],
                        "checksum": file["checksum"]
                    })

            state_id = str(len(states_file_yaml.get("States")))
        else:
            new_state_index = {
                "Update_Date": str(datetime.now()),
                "Additions": cur_index["Files"],
                "Removed": [],
                "Changes": []
            }
            state_id = "0"

        state_path = "%s/states/%s" % (bottle_path, state_id)
        task_entry.remove()
        task_entry = self.operation_manager.new_task(
            _("Creating a restore point …"), False)

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
        except:
            return False

        task_entry.remove()
        task_entry = self.operation_manager.new_task(
            _("Updating index …"), False)

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
            shutil.copyfile(source, target)

        # wait 2s to let the process free the files
        time.sleep(2)

        task_entry.remove()
        task_entry = self.operation_manager.new_task(
            _("Updating states …"), False)

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
                "States": {"0": new_state}
            }

        try:
            with open('%s/states/states.yml' % bottle_path, "w") as states_file:
                yaml.dump(new_state_file, states_file, indent=4)
                states_file.close()
        except:
            return False

        try:
            '''
            Try to create the new index.yml in the bottle's root folder.
            If it fails, it will return False.
            '''
            with open(f'{bottle_path}/states/index.yml', "w") as cur_index_file:
                yaml.dump(cur_index, cur_index_file, indent=4)
                cur_index_file.close()
        except:
            return False

        # update bottle configuation
        self.manager.update_config(config, "State", state_id)
        self.manager.update_config(config, "Versioning", True)

        logging.info(f"New state [{state_id}] created successfully!")

        if update:
            '''
            If the update flag is set, we will update the bottle's 
            states list.
            '''
            self.window.page_details.update_states()

        # update the bottles' list
        time.sleep(2)
        self.manager.update_bottles()

        task_entry.remove()

        if after:
            '''
            If the caller defined a function to be called after the
            process, we will call it.
            '''
            after()

        return True

    def create_bottle_state(
        self,
        config: BottleConfig,
        comment: str = "Not commented",
        update: bool = False,
        no_update: bool = False,
        after: bool = False
    ):
        RunAsync(
            self.async_create_bottle_state, 
            None, 
            [config, comment, update, no_update, after]
        )

    def get_bottle_state_edits(
        self,
        config: BottleConfig,
        state_id: str,
        plain: bool = False
    ) -> dict:
        '''
        This function will return the index.yml content for the given
        state. It will be returned as plain text if the plain flag is
        set, otherwise it will be returned as a dictionary.
        NOTE: maybe this function should be called get_bottle_state_index
        '''
        bottle_path = Runner().get_bottle_path(config)
        try:
            file = open('%s/states/%s/index.yml' % (bottle_path, state_id))
            files = file.read() if plain else yaml.safe_load(file.read())
            file.close()
            return files
        except:
            return {}

    def get_bottle_state_files(
        self,
        config: BottleConfig,
        state_id: str,
        plain: bool = False
    ) -> dict:
        '''
        This function will return the files.yml content for the given
        state. It will be returned as plain text if the plain flag is
        set, otherwise it will be returned as a dictionary.
        '''
        bottle_path = Runner().get_bottle_path(config)

        try:
            file = open('%s/states/%s/files.yml' % (bottle_path, state_id))
            files = file.read() if plain else yaml.safe_load(file.read())
            file.close()
            return files
        except:
            return {}

    def get_bottle_index(self, config: BottleConfig):
        '''
        This function list all files in a bottle and return them
        in a dict (index).
        '''
        bottle_path = Runner().get_bottle_path(config)

        cur_index = {
            "Update_Date": str(datetime.now()),
            "Files": []
        }
        for file in glob("%s/drive_c/**" % bottle_path, recursive=True):
            if not os.path.isfile(file):
                continue

            if file[len(bottle_path)+9:].split("/")[0] in ["users"]:
                continue

            cur_index["Files"].append({
                "file": file[len(bottle_path)+9:],
                "checksum": UtilsFiles().get_checksum(file)
            })
        return cur_index

    def async_set_bottle_state(self, args) -> bool:
        '''
        This function restore the given state to the bottle.
        It compare the state files with bottle ones and restore
        all differences. It will return True if the state is 
        restored successfully, False otherwise.
        NOTE: I know this function is not very optimized and
        well documented, but I'm a bit scared to put my hands
        on it again °_°
        '''
        config, state_id, after = args

        bottle_path = Runner().get_bottle_path(config)

        logging.info(f"Restoring to state: [{state_id}]")

        # get bottle and state indexes
        bottle_index = self.get_bottle_index(config)
        state_index = self.get_bottle_state_files(config, state_id)

        search_sources = list(range(int(state_id)+1))
        search_sources.reverse()

        # check for removed and chaged files
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
                source = "%s/states/%s/drive_c/%s" % (
                    bottle_path, str(i), file["file"])
                if os.path.isfile(source):
                    break
            target = "%s/drive_c/%s" % (bottle_path, file["file"])
            shutil.copyfile(source, target)

        for file in edit_files:
            for i in search_sources:
                source = "%s/states/%s/drive_c/%s" % (
                    bottle_path, str(i), file["file"])
                if os.path.isfile(source):
                    checksum = UtilsFiles().get_checksum(source)
                    if file["checksum"] == checksum:
                        break
            target = "%s/drive_c/%s" % (bottle_path, file["file"])
            shutil.copyfile(source, target)

        # update State in bottle config
        self.manager.update_config(config, "State", state_id)

        # update states
        self.window.page_details.update_states()

        # update bottles
        time.sleep(2)
        self.manager.update_bottles()

        # execute caller function after all
        if after:
            after()

        return True

    def set_bottle_state(
        self, 
        config: BottleConfig, 
        state_id: str, 
        after=False
    ):
        RunAsync(
            self.async_set_bottle_state,
            None,
            [config, state_id, after]
        )

    def list_bottle_states(self, config: BottleConfig) -> dict:
        '''
        This function take all the states from the states.yml file
        of the given bottle and return them as a dict.
        '''
        bottle_path = Runner().get_bottle_path(config)
        states = {}

        try:
            states_file = open('%s/states/states.yml' % bottle_path)
            states_file_yaml = yaml.safe_load(states_file)
            states_file.close()
            states = states_file_yaml.get("States")

            logging.info(
                f"Found [{len(states)}] states for bottle: [{config['Name']}]"
            )
        except:
            logging.error(
                f"Cannot find states.yml file for bottle: [{config['Name']}]"
            )

        return states
