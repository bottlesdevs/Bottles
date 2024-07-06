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
import pathvalidate
from gettext import gettext as _

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import TaskManager, Task, Status
from bottles.backend.utils import yaml
from bottles.backend.utils.file import FileUtils
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


class BackupManager:
    @staticmethod
    def _validate_path(path: str) -> bool:
        """Validate if the path is not None or empty."""
        if not path:
            logging.error(_("No path specified"))
            return False
        return True

    @staticmethod
    def _create_tarfile_external(
        source_path: str, destination_path: str, task: Task
    ):
        """ Creates tarball backup using external tar command. """

        bottle_size = FileUtils.get_path_size(source_path, human=True)

        try:
            import subprocess
            with subprocess.Popen([
                "tar", "--create", "--gzip",
                f"--file=\"{destination_path}\"",
                f"--directory="{source_path}\"",
                "--exclude=\"dosdevices\"",
                "."
            ]) as tar_pid:
                match tar_pid.poll():
                    case None:
                        # Maybe better to have a distinct gettext translation template
                        # for showing backup size and total size properly.
                        # _("Progress {0} / {1}").format(backup_size, bottle_size)
                        backup_size = FileUtils.get_path_size(destination_path, human=True)
                        task.stream_update(
                            received_size=backup_size,
                            total_size=bottle_size,
                            # We never set another status as BackupManager.export_backup is doing the Task cleanup
                            status=Status.RUNNING
                        )
                    case 0:
                        task.subtitle = "Backup completed"
                    case _:
                        logging.error(f"Error creating backup: {e}")
                # Not ideal but Popen.wait() with a timeout value does roughly the same
                # and it would make us have to handle TimeoutExpired exceptions specially.
                time.sleep(0.5)
            return True
        except (FileNotFoundError, PermissionError, CalledProcessError, ValueError) as e:
            logging.error(f"Error creating backup: {e}")
            return False

    @staticmethod
    def _create_tarfile(
        source_path: str, destination_path: str, exclude_filter=None
    ) -> bool:
        """Helper function to create a tar.gz file from a source path."""
        try:
            with tarfile.open(destination_path, "w:gz") as tar:
                os.chdir(os.path.dirname(source_path))
                tar.add(os.path.basename(source_path), filter=exclude_filter)
            return True
        except (FileNotFoundError, PermissionError, tarfile.TarError, ValueError) as e:
            logging.error(f"Error creating backup: {e}")
            return False

    @staticmethod
    def _safe_extract_tarfile(tar_path: str, extract_path: str) -> bool:
        """
        Safely extract a tar.gz file to avoid directory traversal
        vulnerabilities.
        """
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                # Validate each member
                for member in tar.getmembers():
                    member_path = os.path.abspath(
                        os.path.join(extract_path, member.name)
                    )
                    if not member_path.startswith(os.path.abspath(extract_path)):
                        raise Exception("Detected path traversal attempt in tar file")
                tar.extractall(path=extract_path)
            return True
        except (tarfile.TarError, Exception) as e:
            logging.error(f"Error extracting backup: {e}")
            return False

    @staticmethod
    def export_backup(config: BottleConfig, scope: str, path: str) -> Result:
        """
        Exports a bottle backup to the specified path.
        Use the scope parameter to specify the backup type: config, full.
        Config will only export the bottle configuration, full will export
        the full bottle in tar.gz format.
        """
        if not BackupManager._validate_path(path):
            return Result(status=False)

        logging.info(f"Exporting {scope} backup for [{config.Name}] to [{path}]")

        if scope == "config":
            backup_created = config.dump(path).status
        else:
            task_id = TaskManager.add(Task(title=_("Backup {0}").format(config.Name)))
            bottle_path = ManagerUtils.get_bottle_path(config)
            try:
                # Rather poor test to see if tar is available
                os.Popen(["tar", "--version"]).wait(3)
                backup_created = BackupManager._create_tarfile_external(
                    bottle_path, path, task_id)
                logging.info(f"Backup created using tar")
            except FileNotFoundError as e:
                logging.info(f"Backup using tar failed, falling back to original.")
                backup_created = BackupManager._create_tarfile(
                    bottle_path, path, exclude_filter=BackupManager.exclude_filter
                )
            TaskManager.remove(task_id)

        if backup_created:
            logging.info(f"Backup successfully saved to: {path}.")
            return Result(status=True)
        else:
            logging.error("Failed to save backup.")
            return Result(status=False)

    @staticmethod
    def exclude_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
        """
        Filter which excludes some unwanted files from the backup.
        """
        if "dosdevices" in tarinfo.name:
            return None
        return tarinfo

    @staticmethod
    def import_backup(scope: str, path: str) -> Result:
        """
        Imports a backup from the specified path.
        Use the scope parameter to specify the backup type: config, full.
        Config will make a new bottle reproducing the configuration, full will
        import the full bottle from a tar.gz file.
        """
        if not BackupManager._validate_path(path):
            return Result(status=False)

        logging.info(f"Importing backup from: {path}")

        if scope == "config":
            return BackupManager._import_config_backup(path)
        else:
            return BackupManager._import_full_backup(path)

    @staticmethod
    def _import_config_backup(path: str) -> Result:
        task_id = TaskManager.add(Task(title=_("Importing config backup")))
        config_load = BottleConfig.load(path)
        manager = Manager()
        if (
            config_load.status
            and config_load.data
            and manager.create_bottle_from_config(config_load.data)
        ):
            TaskManager.remove(task_id)
            logging.info("Config backup imported successfully.")
            return Result(status=True)
        else:
            TaskManager.remove(task_id)
            logging.error("Failed to import config backup.")
            return Result(status=False)

    @staticmethod
    def _import_full_backup(path: str) -> Result:
        task_id = TaskManager.add(Task(title=_("Importing full backup")))
        if BackupManager._safe_extract_tarfile(path, Paths.bottles):
            Manager().update_bottles()
            TaskManager.remove(task_id)
            logging.info("Full backup imported successfully.")
            return Result(status=True)
        else:
            TaskManager.remove(task_id)
            logging.error("Failed to import full backup.")
            return Result(status=False)

    @staticmethod
    def duplicate_bottle(config: BottleConfig, name: str) -> Result:
        """
        Duplicates the bottle with the specified new name.
        """
        logging.info(f"Duplicating bottle: {config.Name} as {name}")

        sanitized_name = pathvalidate.sanitize_filename(name, platform="universal")
        source_path = ManagerUtils.get_bottle_path(config)
        destination_path = os.path.join(Paths.bottles, sanitized_name)

        return BackupManager._duplicate_bottle_directory(
            config, source_path, destination_path, name
        )

    @staticmethod
    def _duplicate_bottle_directory(
        config: BottleConfig, source_path: str, destination_path: str, new_name: str
    ) -> Result:
        try:
            if not os.path.exists(destination_path):
                os.makedirs(destination_path)
            for item in [
                "drive_c",
                "system.reg",
                "user.reg",
                "userdef.reg",
                "bottle.yml",
            ]:
                source_item = os.path.join(source_path, item)
                destination_item = os.path.join(destination_path, item)
                if os.path.isdir(source_item):
                    shutil.copytree(
                        source_item,
                        destination_item,
                        ignore=shutil.ignore_patterns(".*"),
                        symlinks=True,
                    )
                elif os.path.isfile(source_item):
                    shutil.copy(source_item, destination_item)

            # Update the bottle configuration
            config_path = os.path.join(destination_path, "bottle.yml")
            with open(config_path) as config_file:
                config_data = yaml.load(config_file)
            config_data["Name"] = new_name
            config_data["Path"] = destination_path
            with open(config_path, "w") as config_file:
                yaml.dump(config_data, config_file, indent=4)

            logging.info(f"Bottle duplicated successfully as {new_name}.")
            return Result(status=True)
        except (FileNotFoundError, PermissionError, OSError) as e:
            logging.error(f"Error duplicating bottle: {e}")
            return Result(status=False)
