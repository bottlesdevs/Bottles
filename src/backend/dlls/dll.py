# dll.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import shutil
from typing import NewType
from abc import abstractmethod

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.reg import Reg
from bottles.backend.wine.wineboot import WineBoot

logging = Logger()


class DLLComponent:
    base_path: str = None
    dlls: dict = {}
    version: str = None

    def __init__(self, version: str):
        self.version = version
        self.base_path = self.get_base_path(version)
        self.check()

    @abstractmethod
    def get_base_path(self, version: str):
        pass

    def check(self):
        found = self.dlls.copy()

        for path in self.dlls:
            _path = os.path.join(self.base_path, path)
            if not os.path.exists(_path):
                del found[path]
                continue
            for dll in self.dlls[path]:
                _dll = os.path.join(_path, dll)
                if not os.path.exists(_dll):
                    del found[path][dll]

        if len(found) == 0:
            return False

        self.dlls = found
        return True

    def install(self, config: dict, overrides_only: bool = False, exclude=None):
        dll_in = []
        bundle = {"HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides": []}
        reg = Reg(config)

        if exclude is None:
            exclude = []

        for path in self.dlls:
            for dll in self.dlls[path]:
                if dll not in exclude:
                    dll_name = dll.split('/')[-1].split('.')[0]
                    if overrides_only:
                        dll_in.append(dll_name)
                    else:
                        if self.__install_dll(config, path, dll, False):
                            dll_in.append(dll_name)

        for dll in dll_in:
            bundle["HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides"].append({
                "value": dll,
                "data": "native,builtin"
            })

        reg.import_bundle(bundle)

    def uninstall(self, config: dict, exclude=None):
        reg = Reg(config)
        dll_in = []
        bundle = {"HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides": []}

        if exclude is None:
            exclude = []

        for path in self.dlls:
            for dll in self.dlls[path]:
                if dll not in exclude:
                    dll_name = dll.split('/')[-1].split('.')[0]
                    if self.__uninstall_dll(config, path, dll):
                        dll_in.append(dll_name)

        for dll in dll_in:
            bundle["HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides"].append({
                "value": dll,
                "data": "-"
            })

        reg.import_bundle(bundle)

    @staticmethod
    def __get_sys_path(config, path: str):
        if config["Arch"] == "win32":
            if path in ["x32", "x86"]:
                return "system32"
        if config["Arch"] == "win64":
            if path in ["x64"] or "x86_64" in path:
                return "system32"
            if path in ["x32", "x86"]:
                return "syswow64"
        return None

    def __install_dll(self, config, path: str, dll: str, remove: bool = False):
        dll_name = dll.split('/')[-1]
        bottle = ManagerUtils.get_bottle_path(config)
        bottle = os.path.join(bottle, "drive_c", "windows")
        source = os.path.join(self.base_path, path, dll)
        path = self.__get_sys_path(config, path)

        if path is not None:
            target = os.path.join(bottle, path, dll_name)
        else:
            target = None

        print(f"{source} -> {target}")

        if target is not None:
            if not remove:
                if os.path.exists(target) and not os.path.exists(f"{target}.bck"):
                    shutil.copy(target, f"{target}.bck")
                try:
                    shutil.copyfile(source, target)
                except FileNotFoundError:
                    logging.warning(f"{source} not found")  # TODO: should not be ok but just ignore it for now
                    return False
                '''
                reg.add(
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=dll_name.split('.')[0],
                    data="native,builtin"
                )
                '''
                return True

            if os.path.exists(f"{target}.bck"):
                shutil.move(f"{target}.bck", target)
            elif os.path.exists(target):
                os.remove(target)
            '''
            reg.remove(
                key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                value=dll_name.split('.')[0]
            )
            '''
            return True

    def __uninstall_dll(self, config, path: str, dll: str):
        return self.__install_dll(config, path, dll, remove=True)
