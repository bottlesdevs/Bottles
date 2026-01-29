# backup.py
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
import tarfile
from gettext import gettext as _
from typing import Callable, Optional

import pathvalidate

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import Task, TaskManager
from bottles.backend.utils import yaml
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


class ProgressTrackingFilter:
    """
    A filter wrapper that tracks uncompressed bytes being added to the tar
    and reports progress via a Task.
    """

    def __init__(
        self,
        total_size: int,
        task: Optional[Task] = None,
        base_filter: Optional[Callable] = None,
    ):
        self._total_size = total_size
        self._task = task
        self._base_filter = base_filter
        self._processed = 0
        self._last_percent = -1

    def __call__(self, tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
        # Apply base filter first
        if self._base_filter:
            tarinfo = self._base_filter(tarinfo)
            if tarinfo is None:
                return None

        # Track progress based on file size being added
        if tarinfo.isfile():
            self._processed += tarinfo.size
            self._update_progress()

        return tarinfo

    def _update_progress(self):
        if self._task and self._total_size > 0:
            percent = min(int(self._processed * 100 / self._total_size), 99)
            if percent != self._last_percent:
                self._last_percent = percent
                self._task.subtitle = f"{percent}%"


class BackupManager:
    @staticmethod
    def _validate_path(path: str) -> bool:
        """Validate if the path is not None or empty."""
        if not path:
            logging.error(_("No path specified"))
            return False
        return True

    @staticmethod
    def _calculate_dir_size(
        path: str, exclude_filter: Optional[Callable] = None
    ) -> int:
        """
        Calculate the total size of a directory, respecting the exclude filter.
        """
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            # Apply exclude filter logic to directories
            if exclude_filter:
                # Check if this directory should be excluded
                rel_path = os.path.relpath(dirpath, os.path.dirname(path))
                mock_info = type("TarInfo", (), {"name": rel_path})()
                if exclude_filter(mock_info) is None:
                    dirnames.clear()  # Don't descend into excluded directories
                    continue

            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                # Apply exclude filter to files
                if exclude_filter:
                    rel_path = os.path.relpath(filepath, os.path.dirname(path))
                    mock_info = type("TarInfo", (), {"name": rel_path})()
                    if exclude_filter(mock_info) is None:
                        continue
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
        return total_size

    @staticmethod
    def _create_tarfile(
        source_path: str,
        destination_path: str,
        exclude_filter: Optional[Callable] = None,
        task: Optional[Task] = None,
    ) -> bool:
        """Helper function to create a tar.gz file from a source path."""
        try:
            # Calculate total size for progress tracking
            total_size = 0
            if task:
                task.subtitle = _("Calculating…")
                total_size = BackupManager._calculate_dir_size(
                    source_path, exclude_filter
                )

            os.chdir(os.path.dirname(source_path))

            # Create progress-tracking filter if task is provided
            if task and total_size > 0:
                progress_filter = ProgressTrackingFilter(
                    total_size, task, exclude_filter
                )
                active_filter = progress_filter
            else:
                active_filter = exclude_filter

            with tarfile.open(destination_path, "w:gz") as tar:
                tar.add(os.path.basename(source_path), filter=active_filter)

            if task:
                task.subtitle = "100%"

            return True
        except (FileNotFoundError, PermissionError, tarfile.TarError, ValueError) as e:
            logging.error(f"Error creating backup: {e}")
            return False

    @staticmethod
    def _safe_extract_tarfile(
        tar_path: str, extract_path: str, task: Optional[Task] = None
    ) -> bool:
        """
        Safely extract a tar.gz file to avoid directory traversal
        vulnerabilities.
        """
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                members = tar.getmembers()

                # Validate all members first
                for member in members:
                    member_path = os.path.abspath(
                        os.path.join(extract_path, member.name)
                    )
                    if not member_path.startswith(os.path.abspath(extract_path)):
                        raise Exception("Detected path traversal attempt in tar file")

                if task:
                    # Calculate total size for progress
                    total_size = sum(m.size for m in members if m.isfile())
                    extracted_size = 0
                    last_percent = -1

                    for member in members:
                        tar.extract(member, path=extract_path)
                        if member.isfile():
                            extracted_size += member.size
                            percent = (
                                min(int(extracted_size * 100 / total_size), 99)
                                if total_size > 0
                                else 0
                            )
                            if percent != last_percent:
                                last_percent = percent
                                task.subtitle = f"{percent}%"
                    task.subtitle = "100%"
                else:
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
            task = Task(title=_("Backup {0}").format(config.Name))
            task_id = TaskManager.add(task)
            bottle_path = ManagerUtils.get_bottle_path(config)
            backup_created = BackupManager._create_tarfile(
                bottle_path,
                path,
                exclude_filter=BackupManager.exclude_filter,
                task=task,
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
        task = Task(title=_("Importing full backup"))
        task_id = TaskManager.add(task)
        if BackupManager._safe_extract_tarfile(path, Paths.bottles, task=task):
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
