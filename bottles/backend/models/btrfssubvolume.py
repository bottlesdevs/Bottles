from dataclasses import dataclass
from enum import Enum
import errno
from functools import cached_property
import os
import os.path
import shutil

import btrfsutil

from bottles.backend.models.result import Result

# TODO ask in the GUI, if a bottle should be created as subvolume.
# TODO Add logging

# Internal subvolumes created at initialization time:
_internal_subvolumes = [
    "cache",
    ]

def _delete_subvolume(path):
    try:
        btrfsutil.delete_subvolume(path)
    except btrfsutil.BtrfsUtilError as error:
        if not error.btrfsutilerror == btrfsutil.ERROR_SNAP_DESTROY_FAILED or not error.errno == errno.EPERM:
            raise
        try:
            # Try to delete the subvolume as a normal directory tree. This is
            # in particular needed, if the btrfs filesystem is not mounted with
            # 'user_subvol_rm_allowed' option.
            btrfsutil.set_subvolume_read_only(path, False)
            shutil.rmtree(path)
        except Exception as e:
            # Raise the first error with some appended note
            error.add_note(f"Fallback to 'shutil.rmtree()' failed with: '{e}'")
            raise error


def create_bottle_as_subvolume(bottle_path) -> bool:
    """Create bottle as btrfs subvolume.

    Creates the directory 'bottle_path' as btrfs subvolume and internal
    subvolumes inside of it. Returns True on success and False, if the
    filesystem is not btrfs. For other failures an exception is raised.
    """

    os.makedirs(os.path.dirname(bottle_path), exist_ok=True)
    try:
        btrfsutil.create_subvolume(bottle_path)
        for internal_subvolume in _internal_subvolumes:
            path = os.path.join(bottle_path, internal_subvolume)
            btrfsutil.create_subvolume(path)
    except btrfsutil.BtrfsUtilError as error:
        if not error.btrfsutilerror == btrfsutil.ERROR_NOT_BTRFS:
            raise
        return False
    else:
        return True

class DuplicateResult(Enum):
    NOTHING = 1
    EMPTY_SUBVOLUMES = 2
    SNAPSHOTS_FROM_SOURCE = 3

    def destination_directories_created(self) -> bool:
        return not self == DuplicateResult.NOTHING

    def bottle_contents_is_duplicated(self) -> bool:
        return self == DuplicateResult.SNAPSHOTS_FROM_SOURCE

def duplicate_bottle_as_subvolume(source_path, destination_path) -> DuplicateResult:
    def create_bare_destination() -> DuplicateResult:
        if create_bottle_as_subvolume(destination_path):
            return DuplicateResult.EMPTY_SUBVOLUMES
        else:
            return DuplicateResult.NOTHING

    if not btrfsutil.is_subvolume(source_path):
        return create_bare_destination()
    else:
        try:
            btrfsutil.create_snapshot(source_path, destination_path, read_only=False)
        except btrfsutil.BtrfsUtilError as error:
            match error.btrfsutilerror:
                case btrfsutil.ERROR_NOT_BTRFS:
                    return DuplicateResult.NOTHING
                case btrfsutil.ERROR_SNAP_CREATE_FAILED:
                    return create_bare_destination()
                case _:
                    raise error
        for internal_subvolume in _internal_subvolumes:
            internal_source_path = os.path.join(source_path, internal_subvolume)
            if not btrfsutil.is_subvolume(internal_source_path):
                continue
            internal_destination_path = os.path.join(destination_path, internal_subvolume)
            if os.path.isdir(internal_destination_path):
                os.rmdir(internal_destination_path)
            btrfsutil.create_snapshot(internal_source_path, internal_destination_path, read_only=False)
        return DuplicateResult.SNAPSHOTS_FROM_SOURCE

def try_create_bottle_snapshots_handle(bottle_path):
    """Try to create a bottle snapshots handle.

    Checks if the bottle states can be stored as btrfs snapshots and if no
    states have been stored by FVS versioning system. Returns
    BottleSnapshotsHandle, if checks succeed, None otherwise.
    """
    if not btrfsutil.is_subvolume(bottle_path):
        return None
    if os.path.exists(os.path.join(bottle_path, ".fvs")):
        return None
    return BottleSnapshotsHandle(bottle_path)

@dataclass(frozen=True)
class SnapshotMetaData:
    description: str
    timestamp: float = 0.0

class BottleSnapshotsHandle:
    """Handle the snapshots of a single bottle created as btrfs subvolume.
    """

    def __init__(self, bottle_path):
        """Internal should not be called directly.

        Use try_create_bottle_snapshots_handle() to potentially create an
        instance.
        """
        self._bottle_path = bottle_path
        bottles_dir, bottle_name = os.path.split(bottle_path)
        self._snapshots_directory = os.path.join(bottles_dir, "BottlesSnapshots", bottle_name)

    # Lazily created
    @cached_property
    def _snapshots(self):
        dict_snapshots = {}
        if os.path.exists(self._snapshots_directory):
            with os.scandir(self._snapshots_directory) as it:
                for snapshot in it:
                    if not snapshot.is_dir(follow_symlinks=False):
                        continue
                    if not btrfsutil.is_subvolume(snapshot.path):
                        continue
                    snapshot_id, separator, description = snapshot.name.partition("_")
                    if len(separator) == 0:
                        continue
                    dict_snapshots[int(snapshot_id)] = SnapshotMetaData(description, timestamp=snapshot.stat().st_mtime)
        return dict_snapshots

    def snapshots(self) -> dict:
        """A dictionary of all available snapshots.

        Returns a dictionary from snapshot ID (int) to SnapshotMetaData.
        """
        return self._snapshots.copy()

    def _snapshot_path2(self, snapshot_id: int, description: str):
        return os.path.join(self._snapshots_directory, f"{snapshot_id}_{description}")

    def _snapshot_path(self, snapshot_id: int):
        return self._snapshot_path2(snapshot_id, self._snapshots[snapshot_id].description)

    def _active_snapshot_id_path(self):
        return os.path.join(self._bottle_path, ".active_state_id")

    def _save_active_snapshot_id(self, active_state_id: int):
        with open(self._active_snapshot_id_path(), "w") as file:
            file.write(str(active_state_id))

    def read_active_snapshot_id(self) -> int:
        try:
            with open(self._active_snapshot_id_path(), "r") as file:
                return int(file.read())
        except OSError:
            return -1
 
    def create_snapshot(self, description: str) -> int:
        snapshot_id = max(self._snapshots.keys(), default=-1) + 1
        snapshot_path = self._snapshot_path2(snapshot_id, description)
        os.makedirs(self._snapshots_directory, exist_ok=True)
        btrfsutil.create_snapshot(self._bottle_path, snapshot_path, read_only=True)
        stat = os.stat(snapshot_path)
        self._snapshots[snapshot_id] = SnapshotMetaData(description, stat.st_mtime)
        self._save_active_snapshot_id(snapshot_id)
        return snapshot_id

    def set_state(self, snapshot_id: int):
        """Restore the bottle state from a snapshot.
        """
        tmp_bottle_path = f"{self._bottle_path}-tmp"
        snapshot_path = self._snapshot_path(snapshot_id)
        os.rename(self._bottle_path, tmp_bottle_path)
        try:
            btrfsutil.create_snapshot(snapshot_path, self._bottle_path, read_only=False)
        except btrfsutil.BtrfsUtilError as error:
            os.rename(tmp_bottle_path, self._bottle_path)
            raise error
        for internal_subvolume in _internal_subvolumes:
            source_path = os.path.join(tmp_bottle_path, internal_subvolume)
            if not os.path.exists(source_path) or not btrfsutil.is_subvolume(source_path):
                continue
            destination_path = os.path.join(self._bottle_path, internal_subvolume)
            os.rmdir(destination_path)
            os.rename(source_path, destination_path)
        _delete_subvolume(tmp_bottle_path)
        self._save_active_snapshot_id(snapshot_id)

    def delete_all_snapshots(self) -> None:
        for snapshot_id, metadata in self._snapshots.items():
            snapshot_path = self._snapshot_path2(snapshot_id, metadata.description)
            _delete_subvolume(snapshot_path)
        try:
            os.rmdir(self._snapshots_directory)
        except FileNotFoundError:
            pass

def try_create_bottle_snapshots_versioning_wrapper(bottle_path):
    handle = try_create_bottle_snapshots_handle(bottle_path)
    if not handle:
        return None
    return BottleSnapshotsVersioningWrapper(handle)

class BottleSnapshotsVersioningWrapper:
    def __init__(self, handle: BottleSnapshotsHandle):
        self._handle = handle

    def convert_states(self):
        states = {}
        for snapshot_id, metadata in self._handle.snapshots().items():
            states[snapshot_id] = {"message": metadata.description, "timestamp": metadata.timestamp}
        return states

    def is_initialized(self):
        # Nothing to initialize
        return True

    def re_initialize(self):
        # Nothing to initialize
        pass

    def update_system(self):
        # Nothing to update
        pass

    def create_state(self, message: str) -> Result:
        newly_created_snapshot_id = self._handle.create_snapshot(message)
        return Result(
                status=True,
                data={"state_id": newly_created_snapshot_id, "states": self.convert_states()},
                message="Created new BTRFS snapshot",
        )

    def list_states(self) -> Result:
        active_state_id = self._handle.read_active_snapshot_id()
        return Result(
                status=True,
                data={"state_id": active_state_id, "states": self.convert_states()},
                message="Retrieved list of states",
        )

    def set_state(
        self, state_id: int, after: callable
    ) -> Result:
        self._handle.set_state(state_id)
        if after:
            after()
        return Result(True)
