# gpu.py
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

import subprocess

from enum import Enum
from functools import lru_cache

from bottles.backend.utils.nvidia import get_nvidia_dll_path
from bottles.backend.utils.vulkan import VulkanUtils
import logging


class GPUVendors(Enum):
    AMD = "amd"
    NVIDIA = "nvidia"
    INTEL = "intel"


# noinspection PyTypeChecker
class GPUUtils:
    __vendors = {
        "nvidia": "NVIDIA Corporation",
        "amd": "Advanced Micro Devices, Inc.",
        "intel": "Intel Corporation",
    }

    def __init__(self):
        self.vk = VulkanUtils()

    def list_all(self):
        found = []
        for _vendor in self.__vendors:
            _proc = subprocess.Popen(
                f"lspci | grep '{self.__vendors[_vendor]}'",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
            )
            stdout, stderr = _proc.communicate()

            if len(stdout) > 0:
                found.append(_vendor)

        return found

    @staticmethod
    def assume_discrete(vendors: list):
        if "nvidia" in vendors and "amd" in vendors:
            return {"integrated": "amd", "discrete": "nvidia"}
        if "nvidia" in vendors and "intel" in vendors:
            return {"integrated": "intel", "discrete": "nvidia"}
        if "amd" in vendors and "intel" in vendors:
            return {"integrated": "intel", "discrete": "amd"}
        return {}

    @staticmethod
    def is_nouveau():
        _proc = subprocess.Popen(
            "lsmod | grep nouveau",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        stdout, stderr = _proc.communicate()
        if len(stdout) > 0:
            logging.warning("Nouveau driver detected, this may cause issues")
            return True
        return False

    def get_gpu(self):
        checks = {
            "nvidia": {"query": "(VGA|3D).*NVIDIA"},
            "amd": {"query": "(VGA|3D).*AMD/ATI"},
            "intel": {"query": "(VGA|3D).*Intel"},
        }
        gpus = {
            "nvidia": {
                "vendor": "nvidia",
                "envs": {
                    "__NV_PRIME_RENDER_OFFLOAD": "1",
                    "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                    "__VK_LAYER_NV_optimus": "NVIDIA_only",
                },
                "icd": self.vk.get_vk_icd("nvidia", as_string=True),
                "nvngx_path": get_nvidia_dll_path(),
            },
            "amd": {
                "vendor": "amd",
                "envs": {"DRI_PRIME": "1"},
                "icd": self.vk.get_vk_icd("amd", as_string=True),
            },
            "intel": {
                "vendor": "intel",
                "envs": {"DRI_PRIME": "1"},
                "icd": self.vk.get_vk_icd("intel", as_string=True),
            },
        }
        found = []
        result = {"vendors": {}, "prime": {"integrated": None, "discrete": None}}

        if self.is_nouveau():
            gpus["nvidia"]["envs"] = {"DRI_PRIME": "1"}
            gpus["nvidia"]["icd"] = ""

        for _check in checks:
            _query = checks[_check]["query"]
            _proc = subprocess.Popen(
                f"lspci | grep -iP '{_query}'",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
            )
            stdout, stderr = _proc.communicate()
            if len(stdout) > 0:
                found.append(_check)
                result["vendors"][_check] = gpus[_check]

        if len(found) >= 2:
            _discrete = self.assume_discrete(found)
            if _discrete:
                _integrated = _discrete["integrated"]
                _discrete = _discrete["discrete"]
                result["prime"]["integrated"] = gpus[_integrated]
                result["prime"]["discrete"] = gpus[_discrete]

        return result

    @staticmethod
    @lru_cache
    def is_gpu(vendor: GPUVendors) -> bool:
        _proc = subprocess.Popen(
            f"lspci | grep -iP '{vendor.value}'",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        stdout, stderr = _proc.communicate()
        return len(stdout) > 0
