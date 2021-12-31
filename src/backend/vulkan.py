import os
from glob import glob

from .display import DisplayUtils


class VulkanUtils:

    __vk_icd_dirs = [
        "/usr/share/vulkan",
        "/etc/vulkan",
        "/usr/local/share/vulkan",
        "/usr/local/etc/vulkan"
    ]
    if "FLATPAK_ID" in os.environ:
        __vk_icd_dirs += [
            "/usr/lib/x86_64-linux-gnu/GL/vulkan",
            "/usr/lib/i386-linux-gnu/GL/vulkan",
        ]
    
    def __init__(self):
        self.loaders = self.__get_vk_icd_loaders()

    def __get_vk_icd_loaders(self):
        loaders = {
            "nvidia": [],
            "amd": [],
            "intel": []
        }

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
        vendors = [
            "nvidia",
            "amd",
            "intel"
        ]
        icd = []

        if vendor in vendors:
            icd = self.loaders[vendor]

        if as_string:
            icd = ":".join(icd)

        return icd
