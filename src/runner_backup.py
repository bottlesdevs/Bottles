import os
import yaml
import tarfile

from typing import NewType
from libwine.wine import Wine

from .utils import UtilsLogger, RunAsync
from .runner_globals import BottlesPaths
from .runner_utilities import RunnerUtilities
from .download import DownloadManager

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)


class RunnerBackup:
    
    # Make a bottle backup
    def async_backup_bottle(self, args: list) -> bool:
        window, configuration, scope, path = args
        self.download_manager = DownloadManager(window)
        runner_utils = RunnerUtilities(configuration)
        
        if scope == "configuration":
            # Backup type: configuration
            logging.info(
                f"Backuping configuration: [{configuration['Name']}] in [{path}]")
            try:
                with open(path, "w") as configuration_backup:
                    yaml.dump(configuration, configuration_backup, indent=4)
                    configuration_backup.close()
                backup_created = True
            except:
                backup_created = False

        else:
            # Backup type: full
            logging.info(
                f"Backuping bottle: [{configuration['Name']}] in [{path}]")

            # Add entry to download manager
            download_entry = self.download_manager.new_download(
                _("Backup {0}").format(configuration.get("Name")), False)

            bottle_path = runner_utils.get_bottle_path(configuration)

            try:
                # Create the archive
                with tarfile.open(path, "w:gz") as archive_backup:
                    for root, dirs, files in os.walk(bottle_path):
                        for file in files:
                            archive_backup.add(os.path.join(root, file))
                    archive_backup.close()
                backup_created = True
            except:
                backup_created = False

            # Remove entry from download manager
            download_entry.remove()

        if backup_created:
            logging.info(f"Backup saved in path: {path}.")
            return True

        logging.error(f"Failed to save backup in path: {path}.")

        return False

    def backup_bottle(self,
                      window,
                      configuration: BottleConfig,
                      scope: str,
                      path: str
                      ) -> None:
        RunAsync(self.async_backup_bottle, None, [
                 window, configuration, scope, path])

    def async_import_backup_bottle(self, args: list) -> bool:
        window, scope, path = args
        self.download_manager = DownloadManager(window)
        backup_name = path.split("/")[-1].split(".")
        backup_imported = False

        if scope == "configuration":
            backup_name = backup_name[-2]
        else:
            backup_name = backup_name[-3]

            if backup_name.lower().startswith("backup_"):
                backup_name = backup_name[7:]

            # Add entry to download manager
            download_entry = self.download_manager.new_download(
                _("Importing backup: {0}").format(backup_name), False)
            logging.info(f"Importing backup: {backup_name}")

            try:
                archive = tarfile.open(path)
                archive.extractall(f"{BottlesPaths.bottles}/{backup_name}")
                backup_imported = True
            except:
                backup_imported = False

            # Remove entry from download manager
            download_entry.remove()

        if backup_imported:
            logging.info(f"Backup: [{path}] imported successfully.")

            # Update bottles
            window.runner.update_bottles()
            return True

        logging.error(f"Failed importing backup: [{backup_name}]")
        return False

    def import_backup_bottle(self, window, scope: str, path: str) -> None:
        RunAsync(self.async_import_backup_bottle, None, [window, scope, path])
