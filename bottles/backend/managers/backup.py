# backup.py
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
import shutil
import tarfile
import uuid
import pathvalidate
from typing import NewType
from gettext import gettext as _

from gi.repository import GLib

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils import yaml
from bottles.backend.utils.manager import ManagerUtils
from bottles.frontend.operation import OperationManager

logging = Logger()


class BackupManager:

    @staticmethod
    def export_backup(window, config: BottleConfig, scope: str, path: str) -> Result:
        """
        Exports a bottle backup to the specified path.
        Use the scope parameter to specify the backup type: config, full.
        Config will only export the bottle configuration, full will export
        the full bottle in tar.gz format.
        """
        if path in [None, ""]:
            logging.error(_("No path specified"))
            return Result(status=False)

        BackupManager.operation_manager = OperationManager(window)
        task_id = str(uuid.uuid4())

        logging.info(f"New {scope} backup for [{config.Name}] in [{path}]")

        if scope == "config":
            backup_created = config.dump(path).status
        else:
            GLib.idle_add(
                BackupManager.operation_manager.new_task,
                task_id,
                _("Backup {0}").format(config.Name),
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
            except (FileNotFoundError, PermissionError, tarfile.TarError, ValueError):
                logging.error(f"Error creating backup for [{config.Name}]")
                backup_created = False

            GLib.idle_add(BackupManager.operation_manager.remove_task, task_id)

        if backup_created:
            logging.info(f"New backup saved in path: {path}.", jn=True)
            return Result(status=True)

        logging.error(f"Failed to save backup in path: {path}.")
        return Result(status=False)

    @staticmethod
    def exclude_filter(tarinfo):
        """Filter which excludes some unwanted files from the backup."""
        if "dosdevices" in tarinfo.name:
            return None

        return tarinfo

    @staticmethod
    def import_backup(window, scope: str, path: str, manager: Manager) -> Result:
        """
        Imports a backup from the specified path.
        Use the scope parameter to specify the backup type: config, full.
        Config will make a new bottle reproducing the configuration, full will
        import the full bottle from a tar.gz file.
        """
        if path in [None, ""]:
            logging.error(_("No path specified"))
            return Result(status=False)

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

            config_load = BottleConfig.load(path)
            if config_load.status and manager.create_bottle_from_config(config_load.data):
                import_status = True
            else:
                import_status = False
        else:
            if backup_name.endswith(".tar.gz"):
                backup_name = backup_name[:-7]

            if backup_name.lower().startswith("backup_"):
                # remove the "backup_" prefix if it exists
                backup_name = backup_name[7:]

            try:
                with tarfile.open(path, "r:gz") as tar:
                    def is_within_directory(directory, target):
                        
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                    
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        
                        return prefix == abs_directory
                    
                    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")
                    
                        tar.extractall(path, members, numeric_owner=numeric_owner) 

                    safe_extract(tar, Paths.bottles)
                import_status = True
            except (FileNotFoundError, PermissionError, tarfile.TarError):
                import_status = False

        GLib.idle_add(BackupManager.operation_manager.remove_task, task_id)

        if import_status:
            window.manager.update_bottles()
            logging.info(f"Backup imported: {path}", jn=True)
            return Result(status=True)

        logging.error(f"Failed importing backup: {backup_name}")
        return Result(status=False)

    @staticmethod
    def duplicate_bottle(config, name) -> Result:
        """Duplicates the bottle with the specified new name."""
        logging.info(f"Duplicating bottle: {config.Name} to {name}")

        path = pathvalidate.sanitize_filename(name, platform="universal")
        source = ManagerUtils.get_bottle_path(config)
        dest = os.path.join(Paths.bottles, path)

        source_drive = os.path.join(source, "drive_c")
        dest_drive = os.path.join(dest, "drive_c")

        source_config = os.path.join(source, "bottle.yml")
        dest_config = os.path.join(dest, "bottle.yml")

        if not os.path.exists(dest):
            os.makedirs(dest)

        regs = [
            "system.reg",
            "user.reg",
            "userdef.reg"
        ]

        try:
            for reg in regs:
                source_reg = os.path.join(source, reg)
                dest_reg = os.path.join(dest, reg)
                if os.path.exists(source_reg):
                    shutil.copyfile(source_reg, dest_reg)

            shutil.copyfile(source_config, dest_config)

            with open(dest_config, "r") as config_file:
                config = yaml.load(config_file)
                config["Name"] = name
                config["Path"] = path

            with open(dest_config, "w") as config_file:
                yaml.dump(config, config_file, indent=4)

            shutil.copytree(
                src=source_drive,
                dst=dest_drive,
                ignore=shutil.ignore_patterns(".*"),
                symlinks=True,
                ignore_dangling_symlinks=True
            )
        except (FileNotFoundError, PermissionError, OSError):
            logging.error(f"Failed duplicate bottle: {name}")
            return Result(status=False)

        logging.info(f"Bottle {name} duplicated.", jn=True)
        return Result(status=True)
