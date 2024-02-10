import os
import subprocess
from functools import lru_cache


class DisplayUtils:

    @staticmethod
    @lru_cache
    def get_x_display():
        """Get the X display port."""
        env_var = "DISPLAY"
        ports_range = range(3)

        if os.environ.get(env_var):
            return os.environ.get(env_var)

        for i in ports_range:
            _port = f":{i}"
            _proc = (
                subprocess.Popen(
                    f"xdpyinfo -display :{i}",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                )
                .communicate()[0]
                .decode("utf-8")
                .lower()
            )
            if "x.org" in _proc:
                return _port

        return False

    @staticmethod
    def check_nvidia_device():
        """Check if there is an nvidia device connected"""
        _query = "NVIDIA Corporation".lower()
        _proc = (
            subprocess.Popen(
                "lspci | grep 'VGA'",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
            )
            .communicate()[0]
            .decode("utf-8")
            .lower()
        )

        if _query in _proc:
            return True
        return False

    @staticmethod
    def display_server_type():
        """Return the display server type"""
        return os.environ.get("XDG_SESSION_TYPE", "x11").lower()
