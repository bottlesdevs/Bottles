# backup.py
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
import uuid
import tarfile
import shutil
from typing import NewType
from gettext import gettext as _
from gi.repository import GLib

from bottles.backend.logger import Logger # pyright: reportMissingImports=false
from bottles.backend.managers.manager import Manager
from bottles.backend.models.result import Result
from bottles.backend.globals import Paths
from bottles.backend.utils.manager import ManagerUtils
from bottles.operation import OperationManager

logging = Logger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)


class BackupManager:

    @staticmethod
    def export_backup(
        window,
        config: BottleConfig,
        scope: str,
        path: str
    ) -> bool:
        '''
        This function is used to make a backup of a bottle.
        If the backup type is "config", the backup will be done
        by exporting the bottle.yml file. If the backup type is
        "full", the backup will be done by exporting the entire
        bottle's directory as a tar.gz file.
        It returns True if the backup was successful, False otherwise.
        '''
        BackupManager.operation_manager = OperationManager(window)
        task_id = str(uuid.uuid4())

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
            GLib.idle_add(
                BackupManager.operation_manager.new_task, 
                task_id, 
                _("Backup {0}").format(config.get("Name")),  
                False
            )
            bottle_path = ManagerUtils.get_bottle_path(config)
            try:
                with tarfile.open(path, "w:gz") as tar:
                    parent = os.path.dirname(bottle_path)
                    folder = os.path.basename(bottle_path)
                    os.chdir(parent)
                    tar.add(folder, filter=BackupManager.exclude_filter)
                backup_created = True
            except:
                backup_created = False

            GLib.idle_add(BackupManager.operation_manager.remove_task, task_id)

        if backup_created:
            logging.info(f"Backup saved in path: {path}.")
            return Result(status=True)

        logging.error(f"Failed to save backup in path: {path}.")
        return Result(status=False)
    
    @staticmethod
    def exclude_filter(tarinfo):
        '''
        This function is used to exclude some files from the backup.
        E.g. dosdevices should be excluded as this contains symlinks
        to the real devices and may cause loops.
        '''
        if "dosdevices" in tarinfo.name:
            return None

        return tarinfo

    @staticmethod
    def import_backup(window, scope: str, path: str, manager: Manager) -> bool:
        '''
        This function is used to import a backup of a bottle.
        If the backup type is "config", the configuration will be
        used to replicate the bottle's environment. If the backup
        type is "full", the backup will be extracted in the bottle's
        directory. It returns True if the backup was successful (it 
        will also update the bottles' list), False otherwise.
        '''
        if path is None:
            Result(status=False)
            
        BackupManager.operation_manager = OperationManager(window)

        task_id = str(uuid.uuid4())
        backup_name = os.path.basename(path)
        import_status = False

        GLib.idle_add(
            BackupManager.operation_manager.new_task, 
            task_id, 
            _("Importing backup: {0}").format(backup_name), 
            False
        )
        logging.info(f"Importing backup: {backup_name}")

        if scope == "config":
            '''
            If the backup type is "config", the backup will be used
            to replicate the bottle configuration, else the backup
            will be used to extract the bottle's directory.
            '''
            if backup_name.endswith(".yml"):
                backup_name = backup_name[:-4]

            try:
                with open(path, "r") as config_backup:
                    config = yaml.safe_load(config_backup)
                    config_backup.close()
                
                if manager.create_bottle_from_config(config):
                    import_status = True
            except:
                import_status = False
        else:
            if backup_name.endswith(".tar.gz"):
                backup_name = backup_name[:-7]

            if backup_name.lower().startswith("backup_"):
                # remove the "backup_" prefix if it exists
                backup_name = backup_name[7:]

            try:
                with tarfile.open(path, "r:gz") as tar:
                    tar.extractall(Paths.bottles)
                import_status = True
            except:
                import_status = False

        GLib.idle_add(BackupManager.operation_manager.remove_task, task_id)

        if import_status:
            window.manager.update_bottles()
            logging.info(f"Backup: [{path}] imported successfully.")
            return Result(status=True)

        logging.error(f"Failed importing backup: [{backup_name}]")
        return Result(status=False)

    @staticmethod
    def duplicate_bottle(config, name) -> bool:
        '''
        This function is used to duplicate a bottle.
        The new bottle will be created in the bottles' directory
        using the given name for the bottle's Name and Path.
        '''
        logging.info(f"Duplicating bottle: [{config.get('Name')}] to [{name}]")

        source = ManagerUtils.get_bottle_path(config)
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

            shutil.copytree(
                src=source_drive,
                dst=dest_drive,
                ignore=shutil.ignore_patterns(".*"),
                symlinks=False
            )
        except:
            logging.error(f"Failed duplicate bottle: [{name}]")
            return Result(status=False)

        logging.info(f"Bottle [{name}] duplicated successfully.")
        return Result(status=True)
