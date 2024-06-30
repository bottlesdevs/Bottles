import os
import os.path
import btrfsutil

# Internal subvolumes created at initialization time:
_internal_subvolumes = [
    "cache",
    ]

class BtrfsSubvolumeManager:
    """
    Manager to handle bottles created as btrfs subvolume.
    """

    def __init__(
        self,
        manager,
    ):
        self._manager = manager

    @staticmethod
    def create_bottle_as_subvolume(bottle_path) -> bool:
        """Create bottle as btrfs subvolume.

        Creates the directory 'bottle_path' as btrfs subvolume and internal
        subvolumes inside of it. Returns True on success and False on failure.
        In particular it fails, if the filesystem is not btrfs.
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
