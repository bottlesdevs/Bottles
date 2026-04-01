# vulkan.py
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

import filecmp
import os
import shutil
import subprocess
from functools import lru_cache
from glob import glob


class VulkanUtils:
    __vk_icd_dirs = [
        "/usr/share/vulkan",
        "/etc/vulkan",
        "/usr/local/share/vulkan",
        "/usr/local/etc/vulkan",
    ]
    if "FLATPAK_ID" in os.environ:
        __vk_icd_dirs += [
            "/usr/lib/x86_64-linux-gnu/GL/vulkan",
            "/usr/lib/i386-linux-gnu/GL/vulkan",
        ]

    def __init__(self):
        self.loaders = self.__get_vk_icd_loaders()

    def __get_vk_icd_loaders(self):
        loaders = {"nvidia": [], "amd": [], "intel": []}

        for _dir in self.__vk_icd_dirs:
            _files = glob(f"{_dir}/icd.d/*.json", recursive=True)

            for file in _files:
                if "nvidia" in file.lower():
                    # Workaround for nvidia flatpak bug: https://github.com/flathub/org.freedesktop.Platform.GL.nvidia/issues/112
                    should_skip = False
                    for nvidia_loader in loaders["nvidia"]:
                        try:
                            if filecmp.cmp(nvidia_loader, file):
                                should_skip = True
                                continue
                        except:
                            pass
                    if not should_skip:
                        loaders["nvidia"] += [file]
                elif "amd" in file.lower() or "radeon" in file.lower():
                    loaders["amd"] += [file]
                elif "intel" in file.lower():
                    loaders["intel"] += [file]

        return loaders

    def get_vk_icd(self, vendor: str, as_string=False):
        vendors = ["nvidia", "amd", "intel"]
        icd = []

        if vendor in vendors:
            icd = self.loaders[vendor]

        if as_string:
            icd = ":".join(icd)

        return icd

    @staticmethod
    @lru_cache(maxsize=1)
    def check_support() -> bool:
        """
        Return True if Vulkan is actually functional on this system.
        Uses `vulkaninfo --summary` for a lightweight probe that works both
        on the host and inside the Flatpak sandbox.  Checking only for ICD
        loader files is not reliable inside Flatpak because the runtime may
        ship generic loaders even when the GPU does not support Vulkan.
        """
        if shutil.which("vulkaninfo") is None:
            return False
        try:
            result = subprocess.run(
                ["vulkaninfo", "--summary"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
            # vulkaninfo exits 0 only when at least one GPU is usable.
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def test_vulkan():
        if shutil.which("vulkaninfo") is None:
            return "vulkaninfo tool not found"

        res = (
            subprocess.Popen(
                "vulkaninfo", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
            )
            .communicate()[0]
            .decode("utf-8")
        )

        return res
