import subprocess

from .vulkan import VulkanUtils


class GPUUtils:

    __vendors = {
        "nvidia": "NVIDIA Corporation",
        "amd": "Advanced Micro Devices, Inc.",
        "intel": "Intel Corporation"
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
                shell=True
            )
            stdout, stderr = _proc.communicate()

            if len(stdout) > 0:
                found.append(_vendor)
            
        return found
    
    def assume_discrete(self, vendors: list):
        if "nvidia" in vendors and "amd" in vendors:
            return {"integrated": "amd", "discrete": "nvidia"}
        elif "nvidia" in vendors and "intel" in vendors:
            return {"integrated": "intel", "discrete": "nvidia"}
        elif "amd" in vendors and "intel" in vendors:
            return {"integrated": "intel", "discrete": "amd"}
        return {}


    def get_gpu(self):
        checks = {
            "nvidia": {
                "query": "VGA.*NVIDIA"
            },
            "amd": {
                "query": "VGA.*AMD/ATI"
            },
            "intel": {
                "query": "VGA.*Intel"
            }
        }
        gpus = {
            "nvidia": {
                "vendor": "nvidia",
                "envs": {
                    "__NV_PRIME_RENDER_OFFLOAD": "1",
                    "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                    "__VK_LAYER_NV_optimus": "NVIDIA_only"
                },
                "icd": self.vk.get_vk_icd("nvidia", as_string=True)
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

        for _check in checks:
            _query = checks[_check]["query"]

            _proc = subprocess.Popen(
                f"lspci | grep '{_query}'",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True
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
