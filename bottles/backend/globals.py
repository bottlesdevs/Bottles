# globals.py
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
import shutil
from gi.repository import GLib
from pathlib import Path
from functools import lru_cache
from os import environ

from bottles.backend.logger import Logger
from bottles.backend.utils.display import DisplayUtils
from bottles.backend.managers.data import DataManager
from bottles.backend.health import HealthChecker

logging = Logger()


# xdg data path
xdg_data_home = GLib.get_user_data_dir()

# check if bottles exists in xdg data path
os.makedirs(f"{xdg_data_home}/bottles", exist_ok=True)


def get_apps_dir():
    _dir = f"{xdg_data_home}/applications/"
    if "FLATPAK_ID" in os.environ:
        _dir = f"{Path.home()}/.local/share/applications"
    return _dir

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

def check_vrr_wayland_available():
    """ Check if compositor supports VRR """
    vrr_wayland_support = [
                            "sway",
                            "plasma",
                          ]

    if (environ.get("DESKTOP_SESSION") in vrr_wayland_support and HealthChecker.check_wayland()) or DisplayUtils.display_server_type() == "x11":
        return True
    return False

@lru_cache
class Paths:
    # Icon paths
    icons_user = f"{xdg_data_home}/icons"

    # Local paths
    base = f"{xdg_data_home}/bottles"

    # User applications path
    applications = get_apps_dir()

    # Set errors status
    custom_bottles_path_err = False

    temp = f"{base}/temp"
    runtimes = f"{base}/runtimes"
    winebridge = f"{base}/winebridge"
    runners = f"{base}/runners"
    bottles = f"{base}/bottles"
    steam = f"{base}/steam"
    dxvk = f"{base}/dxvk"
    vkd3d = f"{base}/vkd3d"
    nvapi = f"{base}/nvapi"
    latencyflex = f"{base}/latencyflex"
    templates = f"{base}/templates"
    library = f"{base}/library.yml"

    data = DataManager()
    if data.get("custom_bottles_path"):
        if os.path.exists(data.get("custom_bottles_path")):
            bottles = data.get("custom_bottles_path")
        else:
            logging.error(
                f"Custom bottles path {data.get('custom_bottles_path')} does not exist! Falling back to default path.")
            custom_bottles_path_err = True


class TrdyPaths:
    # External managers paths
    wine = f"{Path.home()}/.wine"
    lutris = f"{Path.home()}/Games"
    playonlinux = f"{Path.home()}/.PlayOnLinux/wineprefix"
    bottlesv1 = f"{Path.home()}/.Bottles"


# Check if some tools are available
gamemode_available = shutil.which("gamemoderun") or False
gamescope_available = shutil.which("gamescope") or False
vkbasalt_available = is_vkbasalt_available()
mangohud_available = shutil.which("mangohud") or False
obs_vkc_available = shutil.which("obs-vkcapture") or False
vmtouch_available = shutil.which("vmtouch") or False
vrr_available = check_vrr_wayland_available()

x_display = DisplayUtils.get_x_display()

# Check if ~/.local/share/applications exists
user_apps_dir = os.path.exists(Paths.applications)
