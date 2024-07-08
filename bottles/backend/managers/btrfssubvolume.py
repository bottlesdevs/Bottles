from dataclasses import dataclass
import errno
from functools import cached_property
import os
import os.path
import shutil

# TODO Properly document and update dependency to libbtrfsutil
# https://github.com/kdave/btrfs-progs/tree/master/libbtrfsutil
import btrfsutil

from bottles.backend.models.result import Result

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

    # TODO delete the snapshots, when the bottle get's deleted

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

    def create_snapshot(self, description: str) -> int:
        snapshot_id = max(self._snapshots.keys(), default=-1) + 1
        snapshot_path = self._snapshot_path2(snapshot_id, description)
        os.makedirs(self._snapshots_directory, exist_ok=True)
        btrfsutil.create_snapshot(self._bottle_path, snapshot_path, read_only=True)
        stat = os.stat(snapshot_path)
        self._snapshots[snapshot_id] = SnapshotMetaData(description, stat.st_mtime)
        return snapshot_id

    def set_state(self, snapshot_id: int):
        """Restore the bottle state from a snapshot.
        """
        tmp_bottle_path = f"{self._bottle_path}-tmp"
        snapshot_path = self._snapshot_path(snapshot_id)
        os.rename(self._bottle_path, tmp_bottle_path)
        btrfsutil.create_snapshot(snapshot_path, self._bottle_path, read_only=False)
        for internal_subvolume in _internal_subvolumes:
            source_path = os.path.join(tmp_bottle_path, internal_subvolume)
            if not os.path.exists(source_path) or not btrfsutil.is_subvolume(source_path):
                continue
            destination_path = os.path.join(self._bottle_path, internal_subvolume)
            os.rmdir(destination_path)
            os.rename(source_path, destination_path)
        _delete_subvolume(tmp_bottle_path)

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
        return true

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
        # TODO Save active state id
        active_state_id = -1
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

    def get_state_files(
        self, state_id: int, plain: bool = False
    ) -> dict:
        raise NotImplementedError

    def get_index(self):
        raise NotImplementedError

class BtrfsSubvolumeManager:
    """
    Manager to handle bottles created as btrfs subvolume.
    """

    # TODO ask in the GUI, if a bottle should be created as subvolume.
    # TODO duplicate bottles as subvolumes. Nice to have, using lightweight
    # subvolume cloning, if the source bottle is a subvolume.
    # TODO Add logging
    # TODO Better error handling
    # TODO Refactoring

    def __init__(
        self,
        manager,
    ):
        self._manager = manager

    @staticmethod
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
