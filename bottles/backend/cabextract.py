# cabextract.py
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

import os
import shlex
import shutil
import subprocess

import logging


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
        files: list | None = None,
        destination: str = "",
    ):
        if files is None:
            files = []

        self.path = path
        self.name = name
        self.files = files
        self.destination = shlex.quote(destination)
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
                    if os.path.exists(os.path.join(self.destination, file)):
                        if os.path.islink(os.path.join(self.destination, file)):
                            os.unlink(os.path.join(self.destination, file))

                    command = [
                        self.cabextract_bin,
                        f"-F '*{file}*'",
                        f"-d {self.destination}",
                        f"-q {self.path}",
                    ]
                    command = " ".join(command)
                    subprocess.Popen(command, shell=True).communicate()

                    if len(file.split("/")) > 1:
                        _file = file.split("/")[-1]
                        _dir = file.replace(_file, "")
                        if not os.path.exists(f"{self.destination}/{_file}"):
                            shutil.move(
                                f"{self.destination}/{_dir}/{_file}",
                                f"{self.destination}/{_file}",
                            )
            else:
                command_list = [
                    self.cabextract_bin,
                    f"-d {self.destination}",
                    f"-q {self.path}",
                ]
                command = " ".join(command_list)
                subprocess.Popen(command, shell=True).communicate()

            logging.info(f"Cabinet {self.name} extracted successfully")
            return True
        except Exception as exception:
            logging.error(f"Error while extracting cab file {self.path}:\n{exception}")

        return False
