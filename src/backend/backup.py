import os
import yaml
import tarfile
import shutil
from typing import NewType
from gettext import gettext as _

from .manager import Manager

from ..utils import UtilsLogger, RunAsync
from .globals import Paths
from .runner import Runner
from ..operation import OperationManager

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)


class RunnerBackup:

    def async_export_backup(self, args: list) -> bool:
        '''
        This function is used to make a backup of a bottle.
        If the backup type is "config", the backup will be done
        by exporting the bottle.yml file. If the backup type is
        "full", the backup will be done by exporting the entire
        bottle's directory as a tar.gz file.
        It returns True if the backup was successful, False otherwise.
        '''
        window, config, scope, path = args
        self.operation_manager = OperationManager(window)

        if scope == "config":
            logging.info(
                f"Backuping config: [{config['Name']}] in [{path}]"
            )
            try:
                with open(path, "w") as config_backup:
                    yaml.dump(config, config_backup, indent=4)
                    config_backup.close()
                backup_created = True
            except:
                backup_created = False

        else:
            logging.info(
                f"Backuping bottle: [{config['Name']}] in [{path}]"
            )
            task_entry = self.operation_manager.new_task(
                file_name=_("Backup {0}").format(config.get("Name")),
                cancellable=False
            )
            bottle_path = Runner().get_bottle_path(config)
            try:
                with tarfile.open(path, "w:gz") as archive_backup:
                    for root, dirs, files in os.walk(bottle_path):
                        for file in files:
                            archive_backup.add(os.path.join(root, file))
                    archive_backup.close()
                backup_created = True
            except:
                backup_created = False

            task_entry.remove()

        if backup_created:
            logging.info(f"Backup saved in path: {path}.")
            return True

        logging.error(f"Failed to save backup in path: {path}.")
        return False

    def export_backup(
        self,
        window,
        config: BottleConfig,
        scope: str,
        path: str
    ):
        RunAsync(self.async_export_backup, None, [window, config, scope, path])

    def async_import_backup(self, args: list) -> bool:
        '''
        This function is used to import a backup of a bottle.
        If the backup type is "config", the configuration will be
        used to replicate the bottle's environement. If the backup
        type is "full", the backup will be extracted in the bottle's
        directory. It returns True if the backup was successful (it 
        will also update the bottles' list), False otherwise.
        '''
        window, scope, path, manager = args
        self.operation_manager = OperationManager(window)
        backup_name = path.split("/")[-1].split(".")
        import_status = False

        task_entry = self.operation_manager.new_task(
            _("Importing backup: {0}").format(backup_name), False
        )
        logging.info(f"Importing backup: {backup_name}")

        if scope == "config":
            '''
            If the backup type is "config", the backup will be used
            to replicate the bottle configuration, else the backup
            will be used to extract the bottle's directory.
            '''
            backup_name = backup_name[-2]
            try:
                with open(path, "r") as config_backup:
                    config = yaml.safe_load(config_backup)
                    config_backup.close()
                
                if manager.create_bottle_from_config(config):
                    import_status = True
            except:
                import_status = False
        else:
            backup_name = backup_name[-3]

            if backup_name.lower().startswith("backup_"):
                # remove the "backup_" prefix if it exists
                backup_name = backup_name[7:]

            try:
                archive = tarfile.open(path)
                archive.extractall(f"{Paths.bottles}/{backup_name}")
                import_status = True
            except:
                import_status = False

        task_entry.remove()

        if import_status:
            window.manager.update_bottles()
            logging.info(f"Backup: [{path}] imported successfully.")
            return True

        logging.error(f"Failed importing backup: [{backup_name}]")
        return False

    def import_backup(self, window, scope: str, path: str, manager: Manager):
        RunAsync(
            self.async_import_backup, None, [window, scope, path, manager]
        )

    def duplicate_bottle(self, config, name) -> bool:
        '''
        This function is used to duplicate a bottle.
        The new bottle will be created in the bottles' directory
        using the given name for the bottle's Name and Path.
        '''
        logging.info(f"Duplicating bottle: [{config.get('Name')}] to [{name}]")

        source = Runner().get_bottle_path(config)
        dest = f"{Paths.bottles}/{name}"

        source_drive = f"{source}/drive_c"
        dest_drive = f"{dest}/drive_c"

        source_config = f"{source}/bottle.yml"
        dest_config = f"{dest}/bottle.yml"

        if not os.path.exists(dest):
            os.makedirs(dest)

        regs = [
            "system.reg",
            "user.reg",
            "userdef.reg"
        ]

        try:
            for reg in regs:
                source_reg = f"{source}/{reg}"
                dest_reg = f"{dest}/{reg}"
                if os.path.exists(source_reg):
                    shutil.copyfile(source_reg, dest_reg)

            shutil.copyfile(source_config, dest_config)

            with open(dest_config, "r") as config_file:
                config = yaml.safe_load(config_file)
                config["Name"] = name
                config["Path"] = name

            with open(dest_config, "w") as config_file:
                yaml.dump(config, config_file, indent=4)

            shutil.copytree(source_drive, dest_drive)
        except:
            logging.error(f"Failed duplicate bottle: [{name}]")
            return False

        logging.info(f"Bottle [{name}] duplicated successfully.")
        return True
