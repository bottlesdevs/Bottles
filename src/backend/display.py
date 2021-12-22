import os
import subprocess


class DisplayUtils:
    
    @staticmethod
    def get_x_display():
        env_var = "DISPLAY"
        ports_range = range(3)

        if os.environ.get(env_var):
            return os.environ.get(env_var)

        for i in ports_range:
            _port = f":{i}"
            _proc = subprocess.Popen(
                f"xdpyinfo -display :{i}",
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                shell=True
            ).communicate()[0].decode("utf-8").lower()
            if "x.org" in _proc:
                return _port
        
        return False
    
    @staticmethod
    def check_nvidia_device():
        _query = "NVIDIA Corporation".lower()
        _proc = subprocess.Popen(
                "lspci | grep 'VGA'",
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                shell=True
            ).communicate()[0].decode("utf-8").lower()
        
        if _query in _proc:
            return True
        return False
    
    @staticmethod
    def prime_support():
        _data = {
            "checks": {
                "nvidia": {
                    "query": "VGA.*NVIDIA",
                    "envs": {
                        "__NV_PRIME_RENDER_OFFLOAD": "1",
                        "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                        "__VK_LAYER_NV_optimus": "NVIDIA_only"
                    }
                },
                "amd": {
                    "query": "VGA.*AMD/ATI"
                },
                "intel": {
                    "query": "VGA.*Intel"
                },
                "default": {
                    "envs": {"DRI_PRIME": "1"}
                }
            }
        }
        _found = {}

        for _check in _data["checks"]:
            if _check == "default":
                continue
            _query = _data["checks"][_check]["query"]
            
            _proc = subprocess.Popen(
                f"lspci | grep '{_query}'",
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                shell=True
            )
            stdout, stderr = _proc.communicate()

            if len(stdout) > 0:
                _found[_check] = True

        if len(_found) >= 2:
            if "nvidia" in _found:
                return _data["checks"]["nvidia"]["envs"]
            else:
                return _data["checks"]["default"]["envs"]
        
        return False

            
        