import bottles.backend.models.btrfssubvolume as btrfssubvolume

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
        return btrfssubvolume.create_bottle_as_subvolume(bottle_path)

    @staticmethod
    def delete_all_snapshots(bottle_path):
        snapshots_handle = btrfssubvolume.try_create_bottle_snapshots_handle(bottle_path)
        if snapshots_handle:
            snapshots_handle.delete_all_snapshots()
