# register.py
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
import uuid
from typing import Optional

from bottles.backend.utils import json


class WinRegister:

    def __init__(self):
        self.path = None
        self.diff = {}
        self.exclude = []
        self.reg_dict = {}

    def new(self, path: str):
        """Create a new WinRegister object with the given path."""

        self.path = path
        self.diff = {}  # will store last diff
        self.exclude = []
        self.reg_dict = self.__parse_dict(path)
        return self

    def __get_header(self):
        """Return the header of the registry file."""
        with open(self.path, "r") as reg:
            header = reg.readlines(2)
            return header

    @staticmethod
    def __parse_dict(path: str):
        """
        Parse the registry file and return a dictionary.
        """
        _dict = {}
        exclude = []  # append here the keys to exclude, not safe

        with open(path, "rb") as _reg:
            content = _reg.read()
            content = content.decode("utf-16")
            cur_line = 0
            regs = content.split("\r")
            print("Total keys:", len(regs))

            for reg in regs:

                if cur_line <= 2:
                    '''
                    Skip the first 4 lines which are the
                    register header.
                    '''
                    cur_line += 1
                    continue

                for line in reg.split("\n"):
                    '''
                    Following checks will check the line format, when
                    one check succeed, continue to the next line.
                    '''

                    if line.startswith("["):
                        '''
                        Check if line format corresponds to a key, if
                        true, create a new key in the dictionary.
                        '''
                        key = line.strip("[]")
                        if any(key.startswith(ex) for ex in exclude):
                            key = None
                            continue

                        _dict[key] = {}
                        continue
                    elif line not in ["", "\n"]:
                        '''
                        Check if line format corresponds to a value, if
                        true get key and value and append to last key.
                        '''
                        if key is None:
                            continue

                        _key = line.split("=")[0]
                        _value = line[len(_key) + 1:]
                        _dict[key][_key] = _value
                        continue

        return _dict

    def compare(self, path: Optional[str] = None, register: object = None):
        """Compare the current register with the given path or register."""
        if path is not None:
            register = WinRegister().new(path)
        elif register is None:
            raise ValueError("No register given")

        diff = self.__get_diff(register)
        self.diff = diff
        return diff

    def __get_diff(self, register: 'WinRegister'):
        """Return the difference between the current register and the given one."""
        diff = {}
        other_reg = register.reg_dict

        for key in self.reg_dict:

            if key not in other_reg:
                diff[key] = self.reg_dict[key]
                continue

            for _key in self.reg_dict[key]:

                if _key not in other_reg[key]:
                    diff[key] = self.reg_dict[key]
                    break

                if self.reg_dict[key][_key] != other_reg[key][_key]:
                    diff[key] = self.reg_dict[key]
                    break

        return diff

    def update(self, diff: Optional[dict] = None):
        """Update the current register with the given diff."""
        if diff is None:
            diff = self.diff  # use last diff

        for key in diff:
            self.reg_dict[key] = diff[key]

        if os.path.exists(self.path):
            '''
            Make a backup before overwriting the register.
            '''
            os.rename(self.path, f"{self.path}.{uuid.uuid4()}.bak")

        with open(self.path, "w") as reg:
            for h in self.__get_header():
                reg.write(h)

            for key in self.reg_dict:
                reg.write(f"[{key}]\n")
                for _key in self.reg_dict[key]:
                    if _key == "time":
                        reg.write(f"#time={self.reg_dict[key][_key]}\n")
                    else:
                        reg.write(f"{_key}={self.reg_dict[key][_key]}\n")
                reg.write("\n")

    def export_json(self, path: str):
        """Export the current register to a json file."""
        with open(path, "w") as json_file:
            json.dump(self.reg_dict, json_file, indent=4)
