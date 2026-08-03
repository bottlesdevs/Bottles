# globals.py
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

import os
import shutil
from pathlib import Path
from typing import Dict

from bottles.backend.utils import json, yaml


def _has_windows_unsafe_component(path: str) -> bool:
    return any(
        part.endswith((".", " "))
        for part in Path(os.path.abspath(path)).parts
        if part != os.path.sep
    )


def _get_wine_compatible_base(path: str) -> str:
    path = os.path.abspath(path)
    if not _has_windows_unsafe_component(path):
        return path

    flatpak_data = "/var/data"
    try:
        data_home = os.path.dirname(path)
        if (
            "FLATPAK_ID" in os.environ
            and os.path.isdir(flatpak_data)
            and os.path.samefile(data_home, flatpak_data)
        ):
            return os.path.join(flatpak_data, os.path.relpath(path, data_home))
    except OSError:
        pass
    return path


class Paths:
    xdg_data_home = os.environ.get(
        "XDG_DATA_HOME", os.path.join(Path.home(), ".local/share")
    )

    # Icon paths
    icons_user = f"{xdg_data_home}/icons"

    # Local paths
    base = _get_wine_compatible_base(f"{xdg_data_home}/bottles")

    # User applications path
    applications = f"{xdg_data_home}/applications/"

    temp = f"{base}/temp"
    runtimes = f"{base}/runtimes"
    winebridge = f"{base}/winebridge"
    runners = f"{base}/runners"
    bottles = f"{base}/bottles"
    steam = f"{base}/steam"
    d7vk = f"{base}/d7vk"
    dxvk = f"{base}/dxvk"
    vkd3d = f"{base}/vkd3d"
    nvapi = f"{base}/nvapi"
    latencyflex = f"{base}/latencyflex"
    templates = f"{base}/templates"
    library = f"{base}/library.yml"
    process_metrics = f"{base}/process_metrics.sqlite"

    @staticmethod
    def is_vkbasalt_available():
        vkbasalt_paths = [
            "/usr/lib/extensions/vulkan/vkBasalt/etc/vkBasalt",
            "/usr/local",
            "/usr/share/vkBasalt",
        ]
        for path in vkbasalt_paths:
            if os.path.exists(path):
                return True
        return False

    @staticmethod
    def get_lsfg_vk_version():
        layer_dirs = [
            path
            for path in os.environ.get("VK_ADD_LAYER_PATH", "").split(os.pathsep)
            if path
        ]
        layer_dirs += [
            "/usr/lib/extensions/vulkan/lsfgvk/share/vulkan/implicit_layer.d",
            f"{Paths.xdg_data_home}/vulkan/implicit_layer.d",
            "/usr/local/share/vulkan/implicit_layer.d",
            "/usr/share/vulkan/implicit_layer.d",
            "/etc/vulkan/implicit_layer.d",
        ]
        for version, manifest in (
            (2, "VkLayer_LSFGVK_frame_generation.json"),
            (1, "VkLayer_LS_frame_generation.json"),
        ):
            if any(
                os.path.isfile(os.path.join(layer_dir, manifest))
                for layer_dir in layer_dirs
            ):
                return version
        return 0


class TrdyPaths:
    # External managers paths
    wine = f"{Path.home()}/.wine"
    lutris = f"{Path.home()}/Games"
    playonlinux = f"{Path.home()}/.PlayOnLinux/wineprefix"
    bottlesv1 = f"{Path.home()}/.Bottles"


# check if bottles exists in xdg data path
os.makedirs(Paths.base, exist_ok=True)

try:
    os.getcwd()
except OSError:
    try:
        os.chdir(Paths.base)
    except OSError:
        pass

def check_flatpak_extension(cmd: str, path: str):
    if "FLATPAK_ID" in os.environ:
        if not os.path.exists(path):
            return False
    return shutil.which(cmd) or False

# Check if some tools are available
gamemode_available = shutil.which("gamemoderun") or False
gamescope_available = check_flatpak_extension("gamescope", "/usr/lib/extensions/vulkan/gamescope/bin/gamescope")
hdr_wsi_available = os.path.exists(
    "/usr/lib/extensions/vulkan/HdrWsi/lib/libVkLayer_hdr_wsi.so"
)
vkbasalt_available = Paths.is_vkbasalt_available()
lsfg_vk_version = Paths.get_lsfg_vk_version()
lsfg_vk_available = bool(lsfg_vk_version)
mangohud_available = check_flatpak_extension("mangohud", "/usr/lib/extensions/vulkan/MangoHud/bin/mangohud")
obs_vkc_available = check_flatpak_extension("obs-vkcapture", "/usr/lib/extensions/vulkan/OBSVkCapture/bin/obs-vkcapture")
vmtouch_available = shutil.which("vmtouch") or False
base_version = ""
if os.path.isfile("/app/manifest.json"):
    with open("/app/manifest.json", mode="r", encoding="utf-8") as file:
        base_version = (
            json.load(file)  # type: ignore
            .get("base-version", "")
            .removeprefix("stable-")
        )

# encoding detection correction, following windows defaults
locale_encodings: Dict[str, str] = {"ja_JP": "cp932", "zh_CN": "gbk"}
