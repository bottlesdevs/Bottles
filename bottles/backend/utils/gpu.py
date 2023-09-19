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
from typing import Dict, List

from bottles.backend.utils.nvidia import get_nvidia_dll_path
from bottles.backend.utils.vulkan import VulkanUtils
from bottles.backend.logger import Logger

logging = Logger()


class GPUVendors(Enum):
    AMD = "amd"
    NVIDIA = "nvidia"
    INTEL = "intel"

# noinspection PyTypeChecker
class GPUUtils:
    _vendor_names = {
        GPUVendors.NVIDIA: "NVIDIA Corporation",
        GPUVendors.AMD: "Advanced Micro Devices, Inc.",
        GPUVendors.INTEL: "Intel Corporation"
    }
    _gpu_classes = [
        "3D controller",
        "Display controller",
        "VGA compatible controller",
    ]

    def __init__(self):
        self.vk = VulkanUtils()

    @staticmethod
    def _get_devices() -> List[Dict[str, str]]:
        """Parses the list of PCI devices returned by `lspci`"""
        _proc = subprocess.Popen(
            ["lspci", "-mmkv"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = _proc.communicate()

        device_list = []
        device_output = {}
        for line in filter(None, stdout.splitlines()):
            if line.startswith("Slot:"):
                if device_output:
                    device_list.append(device_output)
                    device_output = {}

            key, val = line.split(maxsplit=1)
            key = key[:-1].lower()
            device_output[key] = val

        if device_output:
            device_list.append(device_output)
        return device_list

    @staticmethod
    @lru_cache
    def get_gpu_devices() -> List[Dict[str, str]]:
        """
        Returns the list of GPU devices from `lspci`.
        VFIO passthrough devices are excluded.
        """
        devices = GPUUtils._get_devices()

        def predicate(dev: Dict[str, str]) -> bool:
            return dev.get("class") in GPUUtils._gpu_classes \
                and dev.get("driver") != "vfio-pci"

        return list(filter(predicate, devices))

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
    def is_nouveau() -> bool:
        for device in GPUUtils.get_gpu_devices():
            if device.get("driver") == "nouveau":
                logging.warning("Nouveau driver detected, this may cause issues")
                return True
        return False

    def get_gpu(self):
        gpus = {
            "nvidia": {
                "vendor": "nvidia",
                "envs": {
                    "__NV_PRIME_RENDER_OFFLOAD": "1",
                    "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                    "__VK_LAYER_NV_optimus": "NVIDIA_only"
                },
                "icd": self.vk.get_vk_icd("nvidia", as_string=True),
                "nvngx_path": get_nvidia_dll_path()
            },
            "amd": {
                "vendor": "amd",
                "envs": {
                    "DRI_PRIME": "1"
                },
                "icd": self.vk.get_vk_icd("amd", as_string=True)
            },
            "intel": {
                "vendor": "intel",
                "envs": {
                    "DRI_PRIME": "1"
                },
                "icd": self.vk.get_vk_icd("intel", as_string=True)
            }
        }
        found = []
        result = {
            "vendors": {},
            "prime": {
                "integrated": None,
                "discrete": None
            }
        }

        if self.is_nouveau():
            gpus["nvidia"]["envs"] = {"DRI_PRIME": "1"}
            gpus["nvidia"]["icd"] = ""

        for vendor in GPUVendors:
            if GPUUtils.is_gpu(vendor):
                found.append(vendor.value)
                result["vendors"][vendor.value] = gpus[vendor.value]

        if len(found) >= 2:
            _discrete = self.assume_discrete(found)
            if _discrete:
                _integrated = _discrete["integrated"]
                _discrete = _discrete["discrete"]
                result["prime"]["integrated"] = gpus[_integrated]
                result["prime"]["discrete"] = gpus[_discrete]

        return result

    @staticmethod
    def is_gpu(vendor: GPUVendors) -> bool:
        vendor_name = GPUUtils._vendor_names[vendor]

        for device in GPUUtils.get_gpu_devices():
            if vendor_name in device.get("vendor", ""):
                return True
        return False
