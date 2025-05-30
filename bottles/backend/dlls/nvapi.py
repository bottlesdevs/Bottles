# nvapi.py
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

from bottles.backend.dlls.dll import DLLComponent
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils
import logging

from bottles.backend.utils.nvidia import get_nvidia_dll_path


class NVAPIComponent(DLLComponent):
    dlls = {
        "x32": ["nvapi.dll"],
        "x64": ["nvapi64.dll"],
        get_nvidia_dll_path(): ["nvngx.dll", "_nvngx.dll"],
    }

    @staticmethod
    def get_override_keys() -> str:
        # NOTE: Bottles does not override (_)nvngx
        return "nvapi,nvapi64"

    @staticmethod
    def get_base_path(version: str) -> str:
        return ManagerUtils.get_nvapi_path(version)

    @staticmethod
    def check_bottle_nvngx(bottle_path: str, bottle_config: BottleConfig):
        """Checks for the presence of the DLLs provided by the Nvidia driver, and if they're up to date."""

        def md5sum(file):
            hash_md5 = hashlib.md5()
            with open(file, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()

        nvngx_path_bottle = os.path.join(bottle_path, "drive_c", "windows", "system32")
        nvngx_path_system = get_nvidia_dll_path()

        if nvngx_path_system is None:
            logging.error(
                "Nvidia driver libraries haven't been found. DLSS might not work!"
            )
            return

        # Reinstall nvngx if not present (acts as migration for this new patch)
        if not os.path.exists(os.path.join(nvngx_path_bottle, "nvngx.dll")):
            NVAPIComponent(bottle_config.NVAPI).install(bottle_config)
            return

        if not os.path.exists(os.path.join(nvngx_path_bottle, "_nvngx.dll")):
            NVAPIComponent(bottle_config.NVAPI).install(bottle_config)
            return

        # If the system dll is different than the one in the bottle, reinstall them
        # Nvidia driver updates can change this DLL, so this should be checked at each startup
        nvidia_dll_path = get_nvidia_dll_path()
        if nvidia_dll_path is not None:
            if md5sum(os.path.join(nvngx_path_bottle, "nvngx.dll")) != md5sum(
                os.path.join(nvidia_dll_path, "nvngx.dll")
            ):
                NVAPIComponent(bottle_config.NVAPI).install(bottle_config)
                return

            if md5sum(os.path.join(nvngx_path_bottle, "_nvngx.dll")) != md5sum(
                os.path.join(nvidia_dll_path, "_nvngx.dll")
            ):
                NVAPIComponent(bottle_config.NVAPI).install(bottle_config)
                return
