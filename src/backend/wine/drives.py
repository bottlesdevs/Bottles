import os
from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


class Drives:

    def __init__(self, config: dict):
        self.config = config
        bottle = ManagerUtils.get_bottle_path(self.config)
        self.dosdevices_path = f"{bottle}/dosdevices"

    def get_all(self):
        """Get all the drives from the bottle"""
        drives = {}
        if os.path.exists(self.dosdevices_path):
            for drive in os.listdir(self.dosdevices_path):
                if os.path.islink(f"{self.dosdevices_path}/{drive}"):
                    letter = os.path.basename(drive).replace(":", "").upper()
                    if len(letter) == 1 and letter.isalpha():
                        path = os.readlink(f"{self.dosdevices_path}/{drive}")
                        drives[letter] = path
        return drives

    def get_drive(self, letter: str):
        """Get a drive from the bottle"""
        if letter in self.get_all():
            return self.get_all().get(letter)
        return None

    def new_drive(self, letter: str, path: str):
        """Add a new drive to the bottle"""
        letter = f"{letter}:".lower()
        if not os.path.exists(self.dosdevices_path):
            os.makedirs(self.dosdevices_path)
        os.symlink(path, f"{self.dosdevices_path}/{letter}")
        logging.info(f"New drive {letter} added to the bottle")

    def remove_drive(self, letter: str):
        """Remove a drive from the bottle"""
        if letter.upper() in self.get_all():
            os.remove(f"{self.dosdevices_path}/{letter.lower()}:")
            logging.info(f"Drive {letter} removed from the bottle")
