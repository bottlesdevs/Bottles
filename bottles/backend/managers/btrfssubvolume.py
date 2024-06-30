import os
import os.path
import btrfsutil

class BtrfsSubvolumeManager:
    """
    Manager to handle bottles created as btrfs subvolume.
    """

    def __init__(
        self,
        manager,
    ):
        self.manager = manager
