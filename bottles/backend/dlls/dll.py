# dll.py
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
import shutil
from abc import abstractmethod
from copy import deepcopy

import logging
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.enum import Arch
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.reg import Reg


class DLLComponent:
    base_path: str
    dlls: dict = {}
    checked_dlls: dict = {}
    version: str = ""

    def __init__(self, version: str):
        self.version = version
        self.base_path = self.get_base_path(version)
        self.check()

    @staticmethod
    @abstractmethod
    def get_base_path(version: str) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_override_keys() -> str:
        pass

    def check(self) -> bool:
        found = deepcopy(self.dlls)

        if None in self.dlls:
            logging.error(
                f'DLL(s) "{self.dlls[None]}" path haven\'t been found, ignoring...'
            )
            return False

        for path in self.dlls:
            _path = os.path.join(self.base_path, path)
            if not os.path.exists(_path):
                del found[path]
                continue
            for dll in self.dlls[path]:
                _dll = os.path.join(_path, dll)
                if not os.path.exists(_dll):
                    found[path].remove(dll)

        if len(found) == 0:
            return False

        self.checked_dlls = found
        return True

    def install(self, config: BottleConfig, overrides_only: bool = False, exclude=None):
        dll_in = []
        bundle = {"HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides": []}
        reg = Reg(config)

        if exclude is None:
            exclude = []

        if None in self.checked_dlls:
            logging.error(
                f'DLL(s) "{self.checked_dlls[None]}" path haven\'t been found, ignoring...'
            )
            return

        for path in self.checked_dlls:
            for dll in self.checked_dlls[path]:
                if dll not in exclude:
                    dll_name = dll.split("/")[-1].split(".")[0]
                    if overrides_only:
                        dll_in.append(dll_name)
                    else:
                        if self.__install_dll(config, path, dll, False):
                            dll_in.append(dll_name)

        for dll in dll_in:
            bundle["HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides"].append(
                {"value": dll, "data": "native,builtin"}
            )

        reg.import_bundle(bundle)

    def uninstall(self, config: BottleConfig, exclude=None):
        reg = Reg(config)
        dll_in = []
        bundle = {"HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides": []}

        if exclude is None:
            exclude = []

        if None in self.dlls:
            logging.error(
                f'DLL(s) "{self.dlls[None]}" path haven\'t been found, ignoring...'
            )
            return

        for path in self.dlls:
            for dll in self.dlls[path]:
                if dll not in exclude:
                    dll_name = dll.split("/")[-1].split(".")[0]
                    if self.__uninstall_dll(config, path, dll):
                        dll_in.append(dll_name)

        for dll in dll_in:
            bundle["HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides"].append(
                {"value": dll, "data": "-"}
            )

        reg.import_bundle(bundle)

    @staticmethod
    def __get_sys_path(config: BottleConfig, path: str) -> str:
        if config.Arch == Arch.WIN32:
            if path in ["x32", "x86"]:
                return "system32"
        if config.Arch == Arch.WIN64:
            if path in ["x64"] or any(
                arch in path for arch in ("x86_64", "lib64", "lib/")
            ):
                return "system32"
            if path in ["x32", "x86"]:
                return "syswow64"
        return ""

    def __install_dll(
        self, config: BottleConfig, path: str, dll: str, remove: bool = False
    ):
        dll_name = dll.split("/")[-1]
        bottle = ManagerUtils.get_bottle_path(config)
        bottle = os.path.join(bottle, "drive_c", "windows")
        source = os.path.join(self.base_path, path, dll)
        path = self.__get_sys_path(config, path)

        if path != "":
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
                    logging.warning(
                        f"{source} not found"
                    )  # TODO: should not be ok but just ignore it for now
                    return False
                """
                reg.add(
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=dll_name.split('.')[0],
                    data="native,builtin"
                )
                """
                return True

            if os.path.exists(f"{target}.bck"):
                shutil.move(f"{target}.bck", target)
            elif os.path.exists(target):
                os.remove(target)
            """
            reg.remove(
                key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                value=dll_name.split('.')[0]
            )
            """
            return True

    def __uninstall_dll(self, config, path: str, dll: str):
        return self.__install_dll(config, path, dll, remove=True)
