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
import re
import shutil
import tarfile
import tempfile
from concurrent.futures import CancelledError
from datetime import datetime
from gettext import gettext as _
from threading import Event, Lock
from typing import Callable, ClassVar, Optional

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


class _CancellableReader:
    def __init__(self, stream, cancel_event: Event):
        self._stream = stream
        self._cancel_event = cancel_event

    def read(self, size=-1):
        if self._cancel_event.is_set():
            raise CancelledError
        data = self._stream.read(size)
        if self._cancel_event.is_set():
            raise CancelledError
        return data


class _BackupTarFile(tarfile.TarFile):
    def __init__(
        self,
        *args,
        source_path: str,
        cancel_event: Optional[Event] = None,
        **kwargs,
    ):
        self._source_path = source_path
        self._cancel_event = cancel_event
        super().__init__(*args, **kwargs)

    def add(self, name, arcname=None, recursive=True, *, filter=None):
        if self._cancel_event and self._cancel_event.is_set():
            raise CancelledError
        if arcname is None:
            arcname = name

        try:
            tarinfo = self.gettarinfo(name, arcname)
        except FileNotFoundError as error:
            return self._skip_missing(name, error)

        if tarinfo is None:
            return None
        if filter is not None:
            tarinfo = filter(tarinfo)
            if tarinfo is None:
                return None

        if tarinfo.isreg():
            try:
                source = tarfile.bltn_open(name, "rb")
            except FileNotFoundError as error:
                return self._skip_missing(name, error)
            with source:
                self.addfile(tarinfo, source)
        elif tarinfo.isdir():
            self.addfile(tarinfo)
            if recursive:
                try:
                    entries = sorted(os.listdir(name))
                except FileNotFoundError as error:
                    return self._skip_missing(name, error)
                for entry in entries:
                    self.add(
                        os.path.join(name, entry),
                        os.path.join(arcname, entry),
                        recursive,
                        filter=filter,
                    )
        else:
            self.addfile(tarinfo)

    def addfile(self, tarinfo, fileobj=None):
        if self._cancel_event and self._cancel_event.is_set():
            raise CancelledError
        if fileobj is not None and self._cancel_event is not None:
            fileobj = _CancellableReader(fileobj, self._cancel_event)
        return super().addfile(tarinfo, fileobj)

    def _skip_missing(self, name, error):
        if os.path.realpath(name) == self._source_path:
            raise error
        logging.warning(f"Skipping file removed during backup: {name}")


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
        cancel_event: Optional[Event] = None,
    ):
        self._total_size = total_size
        self._task = task
        self._base_filter = base_filter
        self._cancel_event = cancel_event
        self._processed = 0
        self._last_percent = -1

    def __call__(self, tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
        if self._cancel_event and self._cancel_event.is_set():
            raise CancelledError

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
    _BOTTLE_PATH_TOKEN = "%BOTTLE_PATH%"
    _PROGRAM_BACKUP_PATTERN = re.compile(r"^\d{8}-\d{6}-\d{6}$")
    _program_backup_locks: ClassVar[dict[str, Lock]] = {}
    _program_backup_locks_guard: ClassVar[Lock] = Lock()

    @staticmethod
    def _validate_path(path: str) -> bool:
        """Validate if the path is not None or empty."""
        if not path:
            logging.error(_("No path specified"))
            return False
        return True

    @staticmethod
    def _program_backup_timestamp() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S-%f")

    @classmethod
    def _get_program_backup_lock(cls, path: str) -> Lock:
        with cls._program_backup_locks_guard:
            return cls._program_backup_locks.setdefault(path, Lock())

    @classmethod
    def serialize_program_backup_path(
        cls, config: BottleConfig, path: str
    ) -> Optional[str]:
        bottle_path = os.path.abspath(ManagerUtils.get_bottle_path(config))
        selected_path = os.path.abspath(path)
        try:
            if os.path.commonpath(
                (bottle_path, selected_path)
            ) != bottle_path or os.path.commonpath(
                (os.path.realpath(bottle_path), os.path.realpath(selected_path))
            ) != os.path.realpath(bottle_path):
                return None
        except ValueError:
            return None

        relative_path = os.path.relpath(selected_path, bottle_path)
        if relative_path == ".":
            return None
        return os.path.join(cls._BOTTLE_PATH_TOKEN, relative_path)

    @classmethod
    def resolve_program_backup_path(
        cls, config: BottleConfig, path: str
    ) -> Optional[str]:
        if not isinstance(path, str) or not path:
            return None
        token_prefix = f"{cls._BOTTLE_PATH_TOKEN}{os.sep}"
        if path.startswith(token_prefix):
            bottle_path = os.path.abspath(ManagerUtils.get_bottle_path(config))
            resolved = os.path.abspath(
                os.path.join(bottle_path, path.removeprefix(token_prefix))
            )
            try:
                if os.path.commonpath(
                    (bottle_path, resolved)
                ) != bottle_path or os.path.commonpath(
                    (os.path.realpath(bottle_path), os.path.realpath(resolved))
                ) != os.path.realpath(bottle_path):
                    return None
            except ValueError:
                return None
            return resolved
        return None

    @staticmethod
    def _safe_program_backup_name(value: str, fallback: str) -> str:
        name = pathvalidate.sanitize_filename(
            value if isinstance(value, str) else "", platform="universal"
        ).strip()
        if name in (".", ".."):
            return fallback
        return name or fallback

    @classmethod
    def get_program_backup_root(cls, config: BottleConfig, program: dict) -> str:
        settings = program.get("automatic_backup") or {}
        destination = settings.get("destination", "")
        bottle_name = cls._safe_program_backup_name(config.Name, "Bottle")
        program_name = cls._safe_program_backup_name(program.get("name", ""), "Program")
        program_id = cls._safe_program_backup_name(program.get("id", ""), "")
        if program_id:
            program_name = f"{program_name}-{program_id}"
        return os.path.join(destination, bottle_name, program_name)

    @staticmethod
    def is_program_backup_destination_valid(
        config: BottleConfig, destination: str
    ) -> bool:
        if not isinstance(destination, str) or not destination:
            return False
        bottle_path = os.path.abspath(ManagerUtils.get_bottle_path(config))
        destination_path = os.path.abspath(destination)
        real_bottle_path = os.path.realpath(bottle_path)
        real_destination_path = os.path.realpath(destination_path)
        try:
            return not (
                os.path.commonpath((bottle_path, destination_path)) == bottle_path
                or os.path.commonpath((real_bottle_path, real_destination_path))
                == real_bottle_path
            )
        except ValueError:
            return True

    @staticmethod
    def _copy_program_backup_path(source: str, destination: str) -> None:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        if os.path.islink(source):
            os.symlink(
                os.readlink(source),
                destination,
                target_is_directory=os.path.isdir(source),
            )
        elif os.path.isdir(source):
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination, follow_symlinks=False)

    @staticmethod
    def _program_backup_paths_overlap(source: str, destination: str) -> bool:
        if not os.path.isdir(source) or os.path.islink(source):
            return False
        source = os.path.realpath(source)
        destination = os.path.realpath(destination)
        try:
            common = os.path.commonpath((source, destination))
        except ValueError:
            return False
        return common in (source, destination)

    @staticmethod
    def _program_backup_source_contains(source: str, path: str) -> bool:
        if not os.path.isdir(source) or os.path.islink(source):
            return False
        source = os.path.abspath(source)
        path = os.path.abspath(path)
        try:
            return os.path.commonpath((source, path)) == source
        except ValueError:
            return False

    @classmethod
    def _trim_program_backups(cls, root: str, keep: int) -> None:
        generations = sorted(
            [
                entry
                for entry in os.scandir(root)
                if entry.is_dir(follow_symlinks=False)
                and cls._PROGRAM_BACKUP_PATTERN.fullmatch(entry.name)
            ],
            key=lambda entry: entry.name,
        )
        for entry in generations[:-keep]:
            shutil.rmtree(entry.path)

    @classmethod
    def create_program_backup(cls, config: BottleConfig, program: dict) -> Result:
        settings = program.get("automatic_backup")
        if not isinstance(settings, dict) or not settings.get("enabled"):
            return Result(False, message="disabled")

        destination = settings.get("destination")
        paths = settings.get("paths")
        if (
            not isinstance(destination, str)
            or not os.path.isabs(destination)
            or not os.path.isdir(destination)
        ):
            return Result(False, message="The backup folder is unavailable.")
        if not isinstance(paths, list) or not paths:
            return Result(False, message="No backup paths are configured.")

        try:
            keep = int(settings.get("keep", 5))
        except (TypeError, ValueError):
            keep = 5
        keep = min(max(keep, 1), 20)

        bottle_path = os.path.abspath(ManagerUtils.get_bottle_path(config))
        if not cls.is_program_backup_destination_valid(config, destination):
            return Result(
                False,
                message="The backup folder must be outside the bottle.",
            )

        root = cls.get_program_backup_root(config, program)
        try:
            if os.path.commonpath(
                (os.path.realpath(destination), os.path.realpath(root))
            ) != os.path.realpath(destination):
                return Result(
                    False,
                    message="The program backup folder is unavailable.",
                )
        except ValueError:
            return Result(
                False,
                message="The program backup folder is unavailable.",
            )
        if not cls.is_program_backup_destination_valid(config, root):
            return Result(
                False,
                message="The program backup folder must be outside the bottle.",
            )

        selected = []
        for configured_path in paths:
            source = cls.resolve_program_backup_path(config, configured_path)
            if (
                not source
                or not os.path.lexists(source)
                or source in (item[1] for item in selected)
            ):
                continue
            if any(
                cls._program_backup_source_contains(item[1], source)
                for item in selected
            ):
                continue
            selected = [
                item
                for item in selected
                if not cls._program_backup_source_contains(source, item[1])
            ]
            if cls._program_backup_paths_overlap(source, root):
                return Result(
                    False,
                    message="The backup folder overlaps a selected directory.",
                )
            selected.append((configured_path, source))
        if not selected:
            return Result(False, message="No selected backup paths are available.")

        lock = cls._get_program_backup_lock(os.path.realpath(root))
        staging = None
        task = Task(title=_("Backing up {0}").format(program.get("name", "Program")))
        task_id = TaskManager.add(task)
        try:
            with lock:
                os.makedirs(root, exist_ok=True)
                staging = tempfile.mkdtemp(prefix=".backup-", dir=root)
                manifest_paths = []
                for configured_path, source in selected:
                    source_path = os.path.abspath(source)
                    relative_path = os.path.relpath(source_path, bottle_path)

                    target = os.path.join(staging, relative_path)
                    cls._copy_program_backup_path(source, target)
                    manifest_paths.append(
                        {"source": configured_path, "backup": relative_path}
                    )

                timestamp = cls._program_backup_timestamp()
                manifest = {
                    "created": timestamp,
                    "bottle": config.Name,
                    "program": program.get("name", ""),
                    "paths": manifest_paths,
                }
                with open(
                    os.path.join(staging, "backup.yml"),
                    "w",
                    encoding="utf-8",
                ) as manifest_file:
                    yaml.dump(manifest, manifest_file, sort_keys=False)

                final_path = os.path.join(root, timestamp)
                os.replace(staging, final_path)
                staging = None
                try:
                    cls._trim_program_backups(root, keep)
                except OSError as error:
                    logging.warning(f"Failed to rotate automatic backups: {error}")
                logging.info(
                    f"Automatic backup for [{program.get('name', '')}] saved to "
                    f"[{final_path}]."
                )
                return Result(True, data={"path": final_path})
        except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
            logging.error(f"Failed to create automatic backup: {error}")
            return Result(False, message=str(error))
        finally:
            if staging:
                shutil.rmtree(staging, ignore_errors=True)
            TaskManager.remove(task_id)

    @staticmethod
    def _calculate_dir_size(
        path: str,
        exclude_filter: Optional[Callable] = None,
        cancel_event: Optional[Event] = None,
    ) -> int:
        """
        Calculate the total size of a directory, respecting the exclude filter.
        """
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            if cancel_event and cancel_event.is_set():
                raise CancelledError
            # Apply exclude filter logic to directories
            if exclude_filter:
                # Check if this directory should be excluded
                rel_path = os.path.relpath(dirpath, os.path.dirname(path))
                mock_info = type("TarInfo", (), {"name": rel_path})()
                if exclude_filter(mock_info) is None:
                    dirnames.clear()  # Don't descend into excluded directories
                    continue

            for filename in filenames:
                if cancel_event and cancel_event.is_set():
                    raise CancelledError
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
        cancel_event: Optional[Event] = None,
    ) -> bool:
        """Helper function to create a tar.gz file from a source path."""
        temp_path = None
        try:
            source_path = os.path.realpath(source_path)
            destination_path = os.path.abspath(destination_path)
            destination_dir = os.path.dirname(destination_path)
            destinations = (
                os.path.realpath(destination_dir),
                os.path.realpath(destination_path),
            )
            if any(
                os.path.commonpath((source_path, target)) == source_path
                for target in destinations
            ):
                logging.error("The backup destination is inside the bottle.")
                return False

            # Calculate total size for progress tracking
            total_size = 0
            if task:
                task.subtitle = _("Calculating...")
                total_size = BackupManager._calculate_dir_size(
                    source_path, exclude_filter, cancel_event
                )

            if cancel_event and cancel_event.is_set():
                raise CancelledError

            # Create progress-tracking filter if task is provided
            if task and total_size > 0:
                progress_filter = ProgressTrackingFilter(
                    total_size, task, exclude_filter, cancel_event
                )
                active_filter = progress_filter
            else:
                active_filter = exclude_filter

            file_descriptor, temp_path = tempfile.mkstemp(
                prefix=f".{os.path.basename(destination_path)}.",
                suffix=".tmp",
                dir=destination_dir,
            )
            with os.fdopen(file_descriptor, "wb") as temp_file:
                with _BackupTarFile.open(
                    temp_path,
                    "w:gz",
                    fileobj=temp_file,
                    source_path=source_path,
                    cancel_event=cancel_event,
                ) as tar:
                    tar.add(
                        source_path,
                        arcname=os.path.basename(source_path),
                        filter=active_filter,
                    )

            if cancel_event and cancel_event.is_set():
                raise CancelledError

            os.replace(temp_path, destination_path)
            temp_path = None

            if task:
                task.subtitle = "100%"

            return True
        except CancelledError:
            logging.info("Backup cancelled.")
            return False
        except (OSError, tarfile.TarError, ValueError) as e:
            logging.error(f"Error creating backup: {e}")
            return False
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except FileNotFoundError:
                    pass

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
            task = Task(title=_("Backup {0}").format(config.Name), cancellable=True)
            task_id = TaskManager.add(task)
            bottle_path = ManagerUtils.get_bottle_path(config)
            backup_cancelled = False
            try:
                backup_created = BackupManager._create_tarfile(
                    bottle_path,
                    path,
                    exclude_filter=BackupManager.exclude_filter,
                    task=task,
                    cancel_event=task.cancel_event,
                )
                backup_cancelled = not backup_created and task.cancel_event.is_set()
            finally:
                TaskManager.remove(task_id)

            if backup_cancelled:
                return Result(status=False, message="cancelled")

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
        if "lsfg-vk" in tarinfo.name.split("/"):
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

        if not name.strip():
            return Result(status=False, message=_("Bottle name cannot be empty."))

        sanitized_name = pathvalidate.sanitize_filename(
            name.replace(" ", "-"), platform="universal"
        )
        if not sanitized_name:
            return Result(status=False, message=_("Bottle name is not valid."))

        source_path = ManagerUtils.get_bottle_path(config)
        destination_path = os.path.join(Paths.bottles, sanitized_name)

        duplicate_name = name
        suffix = 1
        while os.path.lexists(destination_path):
            duplicate_name = f"{name}__{suffix}"
            destination_path = os.path.join(
                Paths.bottles, f"{sanitized_name}__{suffix}"
            )
            suffix += 1

        return BackupManager._duplicate_bottle_directory(
            config, source_path, destination_path, duplicate_name
        )

    @staticmethod
    def _duplicate_bottle_directory(
        config: BottleConfig, source_path: str, destination_path: str, new_name: str
    ) -> Result:
        destination_created = False
        duplicate_succeeded = False
        try:
            os.makedirs(destination_path)
            destination_created = True
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
            duplicate_succeeded = True
            return Result(status=True)
        except (OSError, shutil.Error) as e:
            logging.error(f"Error duplicating bottle: {e}")
            return Result(status=False, message=str(e))
        finally:
            if destination_created and not duplicate_succeeded:
                shutil.rmtree(destination_path, ignore_errors=True)
