# d7vk.py
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
import filecmp
import json
import os
import shutil
import tempfile
from typing import ClassVar

from bottles.backend.dlls.dll import DLLComponent
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.enum import Arch
from bottles.backend.utils.manager import ManagerUtils


class D7VKComponent(DLLComponent):
    dlls: ClassVar[dict[str, list[str]]] = {"x32": ["ddraw.dll"]}
    state_version = 1

    def __init__(self, version: str):
        self._transaction_created = False
        super().__init__(version)

    def check(self) -> bool:
        if not super().check():
            return False
        source = os.path.join(self.base_path, "x32", "ddraw.dll")
        try:
            valid = os.path.isfile(source) and os.path.getsize(source) > 0
        except OSError:
            valid = False
        if not valid:
            self.checked_dlls = {}
        return valid

    @staticmethod
    def get_override_keys() -> str:
        return "ddraw"

    @staticmethod
    def get_base_path(version: str) -> str:
        return ManagerUtils.get_d7vk_path(version)

    @staticmethod
    def get_wine_path(target: str) -> str:
        name, extension = os.path.splitext(target)
        return f"{name}_{extension}"

    @staticmethod
    def get_backup_path(target: str) -> str:
        return f"{target}.bottles-d7vk.bck"

    @staticmethod
    def get_state_path(target: str) -> str:
        return f"{target}.bottles-d7vk.json"

    @classmethod
    def get_wine_backup_path(cls, target: str) -> str:
        return f"{cls.get_wine_path(target)}.bottles-d7vk.bck"

    @staticmethod
    def get_target_path(config: BottleConfig) -> str:
        system = "system32" if config.Arch == Arch.WIN32 else "syswow64"
        return os.path.join(
            ManagerUtils.get_bottle_path(config),
            "drive_c",
            "windows",
            system,
            "ddraw.dll",
        )

    @staticmethod
    def _copy_atomic(source: str, target: str) -> None:
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(dir=os.path.dirname(target))
            os.close(fd)
            shutil.copyfile(source, temporary)
            os.replace(temporary, target)
        except OSError:
            if temporary:
                with contextlib.suppress(FileNotFoundError):
                    os.remove(temporary)
            raise

    @classmethod
    def _load_state(cls, target: str):
        try:
            with open(cls.get_state_path(target), "r", encoding="utf-8") as state_file:
                state = json.load(state_file)
        except (OSError, ValueError, TypeError):
            return None

        if (
            not isinstance(state, dict)
            or state.get("version") != cls.state_version
            or state.get("phase") not in ("installed", "restored")
            or not isinstance(state.get("target_existed"), bool)
            or not isinstance(state.get("wine_existed"), bool)
        ):
            return None
        return state

    @classmethod
    def _write_state(cls, target: str, state: dict) -> None:
        state_path = cls.get_state_path(target)
        fd, temporary = tempfile.mkstemp(dir=os.path.dirname(state_path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as state_file:
                json.dump(state, state_file)
                state_file.flush()
                os.fsync(state_file.fileno())
            os.replace(temporary, state_path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.remove(temporary)
            raise

    @classmethod
    def has_managed_install(cls, config: BottleConfig) -> bool:
        return cls._load_state(cls.get_target_path(config)) is not None

    def is_installed(self, config: BottleConfig) -> bool:
        target = self.get_target_path(config)
        source = os.path.join(self.base_path, "x32", "ddraw.dll")
        return bool(
            self._load_state(target)
            and os.path.isfile(source)
            and os.path.isfile(target)
            and os.path.isfile(self.get_wine_path(target))
            and filecmp.cmp(source, target, shallow=False)
        )

    def prepare_install(self, target: str, backup: str, backup_created: bool) -> bool:
        wine_path = self.get_wine_path(target)
        wine_backup = self.get_wine_backup_path(target)
        state_path = self.get_state_path(target)
        state = self._load_state(target)

        if state:
            try:
                if state["phase"] == "restored":
                    if state["target_existed"]:
                        if not os.path.exists(backup):
                            if not os.path.isfile(target):
                                return False
                            self._copy_atomic(target, backup)
                    elif os.path.exists(backup):
                        return False

                    if state["wine_existed"]:
                        if not os.path.exists(wine_backup):
                            if not os.path.isfile(wine_path):
                                return False
                            self._copy_atomic(wine_path, wine_backup)
                    elif os.path.exists(wine_backup):
                        return False

                    state["phase"] = "installed"
                    self._write_state(target, state)
                    self._transaction_created = True
                elif backup_created:
                    return False
                if state["target_existed"] != os.path.exists(backup):
                    return False
                if state["wine_existed"] != os.path.exists(wine_backup):
                    return False
                if not os.path.exists(wine_path):
                    source = wine_backup if state["wine_existed"] else backup
                    if not os.path.isfile(source):
                        return False
                    self._copy_atomic(source, wine_path)
                return True
            except OSError:
                return False

        wine_existed = False
        try:
            if os.path.exists(state_path):
                return False
            if os.path.exists(backup) != backup_created:
                return False

            wine_existed = os.path.exists(wine_path)
            if wine_existed:
                if os.path.exists(wine_backup):
                    return False
                self._copy_atomic(wine_path, wine_backup)
            elif not backup_created:
                return False

            self._write_state(
                target,
                {
                    "version": self.state_version,
                    "phase": "installed",
                    "target_existed": backup_created,
                    "wine_existed": wine_existed,
                },
            )
            self._transaction_created = True

            if not wine_existed:
                self._copy_atomic(backup, wine_path)
        except OSError:
            if self._transaction_created:
                with contextlib.suppress(OSError):
                    os.remove(state_path)
            if wine_existed:
                with contextlib.suppress(OSError):
                    os.remove(wine_backup)
            else:
                with contextlib.suppress(OSError):
                    os.remove(wine_path)
            self._transaction_created = False
            return False
        return True

    def cancel_install(self, target: str, backup: str, backup_created: bool) -> None:
        if self._transaction_created:
            try:
                self.finish_uninstall(target, backup)
                if os.path.exists(backup):
                    os.remove(backup)
                self.complete_uninstall(target, backup)
            except OSError:
                return
            return
        super().cancel_install(target, backup, backup_created)

    def complete_install(self, target: str, backup: str) -> None:
        self._transaction_created = False

    def prepare_uninstall(self, target: str, backup: str) -> bool:
        state = self._load_state(target)
        if not state:
            return False
        if state["phase"] == "restored":
            try:
                if state["target_existed"] and not os.path.exists(backup):
                    if not os.path.isfile(target):
                        return False
                    self._copy_atomic(target, backup)
                if state["wine_existed"] and not os.path.exists(
                    self.get_wine_backup_path(target)
                ):
                    wine_path = self.get_wine_path(target)
                    if not os.path.isfile(wine_path):
                        return False
                    self._copy_atomic(wine_path, self.get_wine_backup_path(target))
            except OSError:
                return False
        if state["target_existed"] != os.path.exists(backup):
            return False
        return state["wine_existed"] == os.path.exists(
            self.get_wine_backup_path(target)
        )

    def finish_uninstall(self, target: str, backup: str) -> None:
        wine_path = self.get_wine_path(target)
        wine_backup = self.get_wine_backup_path(target)
        state = self._load_state(target)
        if not state:
            raise OSError("D7VK installation state is missing")

        if state["phase"] == "installed":
            if state["wine_existed"]:
                self._copy_atomic(wine_backup, wine_path)
            else:
                with contextlib.suppress(FileNotFoundError):
                    os.remove(wine_path)

            state["phase"] = "restored"
            self._write_state(target, state)

    def complete_uninstall(self, target: str, backup: str) -> None:
        state = self._load_state(target)
        if not state or state["phase"] != "restored":
            raise OSError("D7VK restoration state is missing")
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.get_wine_backup_path(target))
        os.remove(self.get_state_path(target))
        self._transaction_created = False
