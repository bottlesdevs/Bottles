# cabextract.py
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
import subprocess
from typing import Optional

from bottles.backend.logger import Logger

logging = Logger()


class CabExtract:
    """
    This class is used to extract a Windows cabinet file.
    It takes the cabinet file path and the destination name as input. Then it
    extracts the file in a new directory with the input name under the Bottles'
    temp directory.
    """

    requirements: bool = False
    path: str
    name: str
    files: list
    destination: str

    def __init__(self):
        self.cabextract_bin = shutil.which("cabextract")

    def run(
        self,
        path: str,
        name: str = "",
        files: Optional[list] = None,
        destination: str = "",
    ):
        if files is None:
            files = []

        self.path = path
        self.name = name
        self.files = files
        self.destination = destination
        self.name = self.name.replace(".", "_")

        if not self.__checks():
            return False
        return self.__extract()

    def __checks(self):
        if not os.path.exists(self.path) and "*" not in self.path:
            logging.error(f"Cab file {self.path} not found")
            return False

        return True

    def __extract(self) -> bool:
        if not os.path.exists(self.destination):
            os.makedirs(self.destination)

        try:
            if len(self.files) > 0:
                for file in self.files:
                    """
                    if file already exists as a symlink, remove it
                    preventing broken symlinks
                    """
                    file_path = os.path.join(self.destination, file)
                    if os.path.exists(file_path):
                        if os.path.islink(file_path):
                            os.unlink(file_path)

                    command = [
                        self.cabextract_bin,
                        "-F", f"*{file}*",
                        "-d", self.destination,
                        "-q", self.path,
                    ]
                    subprocess.run(command, check=False)

                    if len(file.split("/")) > 1:
                        _file = file.split("/")[-1]
                        _dir = file.replace(_file, "")
                        if not os.path.exists(os.path.join(self.destination, _file)):
                            shutil.move(
                                os.path.join(self.destination, _dir, _file),
                                os.path.join(self.destination, _file),
                            )
            else:
                command_list = [
                    self.cabextract_bin,
                    "-d", self.destination,
                    "-q", self.path,
                ]
                subprocess.run(command_list, check=False)

            logging.info(f"Cabinet {self.name} extracted successfully")
            return True
        except Exception as exception:
            logging.error(f"Error while extracting cab file {self.path}:\n{exception}")

        return False
