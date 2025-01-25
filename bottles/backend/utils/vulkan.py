# vulkan.py
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
from glob import glob
import shutil
import subprocess


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
    def check_support():
        return True

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
