# file.py
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

import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Union


class FileUtils:
    """
    This class provide some useful methods to work with files.
    Like get checksum, human size, etc.
    """

    @staticmethod
    def get_checksum(file):
        """
        This function returns the MD5 checksum of the given file.
        """
        checksum = hashlib.md5()

        try:
            with open(file, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    checksum.update(chunk)
            return checksum.hexdigest().lower()
        except FileNotFoundError:
            return None

    @staticmethod
    def use_insensitive_ext(string):
        """Converts a glob pattern into a case-insensitive glob pattern"""
        ext = string.split('.')[1]
        globlist = ["[%s%s]" % (c.lower(), c.upper()) for c in ext]
        return '*.%s' % ''.join(globlist)

    @staticmethod
    def get_human_size(size: float) -> str:
        """Returns a human readable size from a given float size"""
        for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
            if abs(size) < 1024.0:
                return f"{size:3.1f}{unit}B"
            size /= 1024.0
        return f"{size:.1f}YiB"

    @staticmethod
    def get_human_size_legacy(size: float) -> str:
        """Returns a human readable size from a given float size"""
        for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
            if abs(size) < 1024.0:
                return "%3.1f%s%s" % (size, unit, 'B')
            size /= 1024.0

        return "%.1f%s%s" % (size, 'Yi', 'B')

    def get_path_size(self, path: str, human: bool = True) -> Union[str, float]:
        """
        Returns the size of a given path. If human is True, returns as a
        human-readable size.
        """
        p = Path(path)
        size = sum(f.stat().st_size for f in p.glob('**/*') if f.is_file())

        if human:
            return self.get_human_size(size)

        return size

    def get_disk_size(self, human: bool = True) -> dict:
        """
        Returns the size of the disk. If human is True, returns as a
        human-readable size.
        """
        disk_total, disk_used, disk_free = shutil.disk_usage('/')

        if human:
            disk_total = self.get_human_size(disk_total)
            disk_used = self.get_human_size(disk_used)
            disk_free = self.get_human_size(disk_free)

        return {
            "total": disk_total,
            "used": disk_used,
            "free": disk_free,
        }

    @staticmethod
    def wait_for_files(files: list, timeout: int = .5) -> bool:
        """Wait for a file to be created or modified."""
        for file in files:
            if not os.path.isfile(file):
                return False

            while not os.path.exists(file):
                time.sleep(timeout)

        return True
