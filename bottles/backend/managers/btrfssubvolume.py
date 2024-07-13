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
