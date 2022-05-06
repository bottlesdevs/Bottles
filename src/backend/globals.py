# globals.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import shutil
from pathlib import Path
from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.utils.display import DisplayUtils
from bottles.backend.managers.data import DataManager

logging = Logger()


class API:
    notifications = "https://raw.githubusercontent.com/bottlesdevs/data/main/notifications.yml"

# xdg data path
xdg_data_home = os.environ.get("XDG_DATA_HOME", f"{Path.home()}/.local/share")

# check if bottles exists in xdg data path
os.makedirs(f"{xdg_data_home}/bottles", exist_ok=True)


def get_apps_dir():
    _dir = f"{xdg_data_home}/applications/"
    if "FLATPAK_ID" in os.environ:
        _dir = f"{Path.home()}/.local/share/applications"
    return _dir


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
    layers = f"{base}/layers"
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
    wine = f"{xdg_data_home}/.wine"
    lutris = f"{xdg_data_home}*/Games"
    playonlinux = f"{xdg_data_home}/.PlayOnLinux/wineprefix"
    bottlesv1 = f"{xdg_data_home}/.Bottles"


# Check if some tools are available
gamemode_available = shutil.which("gamemoderun") or False
gamescope_available = shutil.which("gamescope") or False
mangohud_available = shutil.which("mangohud") or False
obs_vkc_available = shutil.which("obs-vkcapture") or False

x_display = DisplayUtils.get_x_display()

# Check if ~/.local/share/applications exists
user_apps_dir = os.path.exists(Paths.applications)
