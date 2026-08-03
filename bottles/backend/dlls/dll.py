# dll.py
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

import contextlib
import os
import shutil
import tempfile
from abc import abstractmethod
from copy import deepcopy

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.enum import Arch
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.reg import Reg

logging = Logger()


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

    @staticmethod
    def get_backup_path(target: str) -> str:
        return f"{target}.bck"

    def prepare_install(self, target: str, backup: str, backup_created: bool) -> bool:
        return True

    def cancel_install(self, target: str, backup: str, backup_created: bool) -> None:
        if backup_created:
            with contextlib.suppress(FileNotFoundError):
                os.remove(backup)

    def complete_install(self, target: str, backup: str) -> None:
        pass

    def finish_uninstall(self, target: str, backup: str) -> None:
        pass

    def complete_uninstall(self, target: str, backup: str) -> None:
        pass

    def prepare_uninstall(self, target: str, backup: str) -> bool:
        return True

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
            if not found[path]:
                del found[path]

        if len(found) == 0:
            return False

        self.checked_dlls = found
        return True

    def install(self, config: BottleConfig, overrides_only: bool = False, exclude=None):
        dll_in = []
        success = True
        bundle = {"HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides": []}
        reg = Reg(config)

        if exclude is None:
            exclude = []

        if None in self.checked_dlls:
            logging.error(
                f'DLL(s) "{self.checked_dlls[None]}" path haven\'t been found, ignoring...'
            )
            return False

        for path in self.checked_dlls:
            for dll in self.checked_dlls[path]:
                if dll not in exclude:
                    dll_name = dll.split("/")[-1].split(".")[0]
                    if overrides_only:
                        dll_in.append(dll_name)
                    else:
                        if self.__install_dll(config, path, dll, False):
                            dll_in.append(dll_name)
                        else:
                            success = False

        for dll in dll_in:
            bundle["HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides"].append(
                {"value": dll, "data": "native,builtin"}
            )

        registry_result = reg.import_bundle(bundle)
        if registry_result is not None and not registry_result.ok:
            success = False
        return success

    def uninstall(self, config: BottleConfig, exclude=None):
        reg = Reg(config)
        dll_in = []
        success = True
        bundle = {"HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides": []}

        if exclude is None:
            exclude = []

        if None in self.dlls:
            logging.error(
                f'DLL(s) "{self.dlls[None]}" path haven\'t been found, ignoring...'
            )
            return False

        for path in self.dlls:
            for dll in self.dlls[path]:
                if dll not in exclude:
                    dll_name = dll.split("/")[-1].split(".")[0]
                    if self.__uninstall_dll(config, path, dll):
                        dll_in.append(dll_name)
                    else:
                        success = False

        for dll in dll_in:
            bundle["HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides"].append(
                {"value": dll, "data": "-"}
            )

        registry_result = reg.import_bundle(bundle)
        if registry_result is not None and not registry_result.ok:
            success = False
        return success

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
            backup = self.get_backup_path(target)
            if not remove:
                backup_created = False
                temporary = None
                try:
                    if os.path.exists(target) and not os.path.exists(backup):
                        shutil.copy(target, backup)
                        backup_created = True
                    if not self.prepare_install(target, backup, backup_created):
                        self.cancel_install(target, backup, backup_created)
                        return False
                    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(target))
                    os.close(fd)
                    shutil.copyfile(source, temporary)
                    os.replace(temporary, target)
                    self.complete_install(target, backup)
                except OSError:
                    if temporary:
                        with contextlib.suppress(FileNotFoundError):
                            os.remove(temporary)
                    self.cancel_install(target, backup, backup_created)
                    logging.warning(f"Failed to install {source}")
                    return False
                """
                reg.add(
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=dll_name.split('.')[0],
                    data="native,builtin"
                )
                """
                return True

            if not self.prepare_uninstall(target, backup):
                return False

            temporary = None
            backup_used = False
            try:
                if os.path.exists(backup):
                    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(target))
                    os.close(fd)
                    shutil.copyfile(backup, temporary)
                    os.replace(temporary, target)
                    backup_used = True
                elif os.path.exists(target):
                    os.remove(target)
                self.finish_uninstall(target, backup)
                if backup_used:
                    os.remove(backup)
                self.complete_uninstall(target, backup)
            except OSError:
                if temporary:
                    with contextlib.suppress(FileNotFoundError):
                        os.remove(temporary)
                logging.warning(f"Failed to uninstall {target}")
                return False
            """
            reg.remove(
                key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                value=dll_name.split('.')[0]
            )
            """
            return True

    def __uninstall_dll(self, config, path: str, dll: str):
        return self.__install_dll(config, path, dll, remove=True)
