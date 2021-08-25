import os
import yaml
import time
import shutil

from typing import NewType

from glob import glob
from datetime import datetime

from ..download import DownloadManager
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

    # Create new bottle state
    def async_create_bottle_state(self, args: list) -> bool:
        config, comment, update, no_update, after = args

        logging.info(
            f"Creating new state for bottle: [{config['Name']}] …")

        self.download_manager = DownloadManager(self.window)

        bottle_path = Runner().get_bottle_path(config)
        first = False if os.path.isdir(f"{bottle_path}/states/") else True

        # List all bottle files
        current_index = self.get_bottle_index(config)

        download_entry = self.download_manager.new_download(
            _("Generating state files index …"), False)

        # If it is not the first state, compare files with the previous one
        if not first:
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
            current_temp_files = [
                tuple([f["file"], f["checksum"]])
                for f in current_index["Files"]
            ]
            additions = set(current_temp_files) - set(state_temp_files)
            removed = set(state_temp_files) - set(current_temp_files)

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

            for file in current_index["Files"]:
                if file["checksum"] not in state_temp_checksums:
                    new_state_index["Changes"].append({
                        "file": file["file"],
                        "checksum": file["checksum"]
                    })

            state_id = str(len(states_file_yaml.get("States")))
        else:
            new_state_index = {
                "Update_Date": str(datetime.now()),
                "Additions": current_index["Files"],
                "Removed": [],
                "Changes": []
            }
            state_id = "0"

        state_path = "%s/states/%s" % (bottle_path, state_id)

        download_entry.destroy()
        download_entry = self.download_manager.new_download(
            _("Creating a restore point …"), False)

        try:
            # Make state structured path
            os.makedirs("%s/states/%s/drive_c" %
                        (bottle_path, state_id), exist_ok=True)

            # Save index.yml with state edits
            with open("%s/index.yml" % (state_path),
                      "w") as state_index_file:
                yaml.dump(new_state_index, state_index_file, indent=4)
                state_index_file.close()

            # Save files.yml with bottle files
            with open("%s/files.yml" % (state_path),
                      "w") as state_files_file:
                yaml.dump(current_index, state_files_file, indent=4)
                state_files_file.close()
        except:
            return False

        download_entry.destroy()
        download_entry = self.download_manager.new_download(
            _("Updating index …"), False)

        # Copy indexed files in the new state path
        for file in current_index["Files"]:
            os.makedirs("{0}/drive_c/{1}".format(
                state_path,
                "/".join(file["file"].split("/")[:-1])), exist_ok=True)
            source = "{0}/drive_c/{1}".format(bottle_path, file["file"])
            target = "{0}/drive_c/{1}".format(state_path, file["file"])
            shutil.copyfile(source, target)

        time.sleep(5)

        download_entry.destroy()
        download_entry = self.download_manager.new_download(
            _("Updating states …"), False)

        # Update the states.yml file
        new_state = {
            "Creation_Date": str(datetime.now()),
            "Comment": comment,
            # "Files": [file["file"] for file in current_index["Files"]]
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

        # Create new index.yml in the states root
        try:
            with open('%s/states/index.yml' % bottle_path,
                      "w") as current_index_file:
                yaml.dump(current_index, current_index_file, indent=4)
                current_index_file.close()
        except:
            return False

        # Update State in bottle config
        self.manager.update_config(config, "State", state_id)
        self.manager.update_config(config, "Versioning", True)

        logging.info(f"New state [{state_id}] created successfully!")

        # Update states
        if update:
            self.window.page_details.update_states()

        # Update bottles
        time.sleep(2)
        self.manager.update_bottles()

        download_entry.destroy()

        # Execute caller function after all
        if after:
            after()

        return True

    def create_bottle_state(self,
                            config: BottleConfig,
                            comment: str = "Not commented",
                            update: bool = False,
                            no_update: bool = False,
                            after: bool = False
                            ) -> None:
        RunAsync(self.async_create_bottle_state, None, [
                 config, comment, update, no_update, after])

    # Get edits for a state
    def get_bottle_state_edits(self,
                               config: BottleConfig,
                               state_id: str,
                               plain: bool = False
                               ) -> dict:
        bottle_path = Runner().get_bottle_path(config)

        try:
            file = open('%s/states/%s/index.yml' % (bottle_path, state_id))
            files = file.read() if plain else yaml.safe_load(file.read())
            file.close()
            return files
        except:
            return {}

    # Get files for a state
    def get_bottle_state_files(self,
                               config: BottleConfig,
                               state_id: str,
                               plain: bool = False
                               ) -> dict:
        bottle_path = Runner().get_bottle_path(config)

        try:
            file = open('%s/states/%s/files.yml' % (bottle_path, state_id))
            files = file.read() if plain else yaml.safe_load(file.read())
            file.close()
            return files
        except:
            return {}

    # Get all bottle files
    def get_bottle_index(self, config: BottleConfig):
        bottle_path = Runner().get_bottle_path(config)

        current_index = {
            "Update_Date": str(datetime.now()),
            "Files": []
        }
        for file in glob("%s/drive_c/**" % bottle_path, recursive=True):
            if not os.path.isfile(file):
                continue
            if file[len(bottle_path)+9:].split("/")[0] in ["users"]:
                continue

            current_index["Files"].append({
                "file": file[len(bottle_path)+9:],
                "checksum": UtilsFiles().get_checksum(file)})
        return current_index

    # Set state for a bottle
    def async_set_bottle_state(self, args) -> bool:
        config, state_id, after = args

        bottle_path = Runner().get_bottle_path(config)

        logging.info(f"Restoring to state: [{state_id}]")

        # Get indexes
        bottle_index = self.get_bottle_index(config)
        state_index = self.get_bottle_state_files(config, state_id)

        search_sources = list(range(int(state_id)+1))
        search_sources.reverse()

        # Check for removed and chaged files
        remove_files = []
        edit_files = []
        for file in bottle_index.get("Files"):
            if file["file"] not in [file["file"] for file in state_index.get("Files")]:
                remove_files.append(file)
            elif file["checksum"] not in [file["checksum"] for file in state_index.get("Files")]:
                edit_files.append(file)
        logging.info(f"[{len(remove_files)}] files to remove.")
        logging.info(f"[{len(edit_files)}] files to replace.")

        # Check for new files
        add_files = []
        for file in state_index.get("Files"):
            if file["file"] not in [file["file"] for file in bottle_index.get("Files")]:
                add_files.append(file)
        logging.info(f"[{len(add_files)}] files to add.")

        # Perform file updates
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

        # Update State in bottle config
        self.manager.update_config(config, "State", state_id)

        # Update states
        self.window.page_details.update_states()

        # Update bottles
        time.sleep(2)
        self.manager.update_bottles()

        # Execute caller function after all
        if after:
            after()

        return True

    def set_bottle_state(self,
                         config: BottleConfig,
                         state_id: str,
                         after=False
                         ) -> None:
        RunAsync(self.async_set_bottle_state, None,
                 [config, state_id, after])

    def list_bottle_states(self, config: BottleConfig) -> dict:
        bottle_path = Runner().get_bottle_path(config)
        states = {}

        try:
            states_file = open('%s/states/states.yml' % bottle_path)
            states_file_yaml = yaml.safe_load(states_file)
            states_file.close()
            states = states_file_yaml.get("States")

            logging.info(
                f"Found [{len(states)}] states for bottle: [{config['Name']}]")
        except:
            logging.error(
                f"Cannot find states.yml file for bottle: [{config['Name']}]")

        return states
