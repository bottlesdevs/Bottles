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
from bottles.utils import UtilsLogger # pyright: reportMissingImports=false
from bottles.backend.utils.display import DisplayUtils


logging = UtilsLogger()

class API:
    notifications = "https://raw.githubusercontent.com/bottlesdevs/data/main/notifications.yml"
    
class Samples:

    data = {
        "notifications": []
    }

    config = {
        "Name": "",
        "Arch": "win64",
        "Windows": "win10",
        "Runner": "",
        "WorkingDir": "",
        "DXVK": "",
        "NVAPI": "",
        "VKD3D": "",
        "Path": "",
        "Custom_Path": False,
        "Environment": "",
        "Creation_Date": "",
        "Update_Date": "",
        "Versioning": False,
        "State": 0,
        "Parameters": {
            "dxvk": False,
            "dxvk_hud": False,
            "dxvk_nvapi": False,
            "vkd3d": False,
            "gamemode": False,
            "gamescope": False,
            "gamescope_game_width": 0,
            "gamescope_game_height": 0,
            "gamescope_window_width": 0,
            "gamescope_window_height": 0,
            "gamescope_fps": 0,
            "gamescope_fps_no_focus": 0,
            "gamescope_scaling": False,
            "gamescope_borderless": False,
            "gamescope_fullscreen": True,
            "sync": "wine",
            "fsr": False,
            "fsr_level": 5,
            "aco_compiler": False,
            "discrete_gpu": False,
            "virtual_desktop": False,
            "virtual_desktop_res": "1280x720",
            "pulseaudio_latency": False,
            "fullscreen_capture": False,
            "fixme_logs": False,
            "use_runtime": False,
        },
        "Environment_Variables": {},
        "Installed_Dependencies": [],
        "DLL_Overrides": {},
        "External_Programs": {},
        "Uninstallers": {},
        "Latest_Executables": []
    }

    environments = {
        "gaming": {
            "Runner": "wine",
            "Parameters": {
                "dxvk": True,
                # "nvapi": True,
                "vkd3d": False,
                "sync": "esync",
                "fsr": False,
                "discrete_gpu": True,
                "pulseaudio_latency": True
            },
            "Installed_Dependencies": [
                "d3dx9",
                "msls31",
                "arial32",
                "times32",
                "courie32",
                "d3dcompiler_43",
                "d3dcompiler_47"
            ]
        },
        "application": {
            "Runner": "wine",
            "Parameters": {
                "dxvk": True,
                "vkd3d": True
            },
            "Installed_Dependencies": [
                "arial32",
                "times32",
                "courie32",
                "mono",
                #"dotnet40",
                #"dotnet48"
            ]
        },
        "layered": {
            "Runner": "wine",
            "Layers": {}
        },
    }


class BottlesRepositories:
    components = "https://raw.githubusercontent.com/bottlesdevs/components/main/"
    components_index = f"{components}/index.yml"

    dependencies = "https://raw.githubusercontent.com/bottlesdevs/dependencies/main/"
    dependencies_index = f"{dependencies}/index.yml"

    installers = "https://raw.githubusercontent.com/bottlesdevs/programs/main/"
    installers_index = f"{installers}/index.yml"

    if "TESTING_REPOS" in os.environ and int(os.environ["TESTING_REPOS"]) == 1:
            dependencies_index = f"{dependencies}/testing.yml"
            components_index = f"{components}/testing.yml"
    
    if "LOCAL_COMPONENTS" in os.environ:
        if os.path.exists(f"{os.environ['LOCAL_COMPONENTS']}/index.yml"):
            logging.info(f"Using a local components repository: {os.environ['LOCAL_COMPONENTS']}")
            components = f"file://{os.environ['LOCAL_COMPONENTS']}/"
            components_index = f"{components}/index.yml"
        else:
            logging.error(f"Local components path does not exist: {os.environ['LOCAL_COMPONENTS']}")
    
    if "LOCAL_DEPENDENCIES" in os.environ:
        if os.path.exists(f"{os.environ['LOCAL_DEPENDENCIES']}/index.yml"):
            logging.info(f"Using a local dependencies repository: {os.environ['LOCAL_DEPENDENCIES']}")
            dependencies = f"file://{os.environ['LOCAL_DEPENDENCIES']}/"
            dependencies_index = f"{dependencies}/index.yml"
        else:
            logging.error(f"Local dependencies path does not exist: {os.environ['LOCAL_DEPENDENCIES']}")
    
    if "LOCAL_INSTALLERS" in os.environ:
        if os.path.exists(f"{os.environ['LOCAL_INSTALLERS']}/index.yml"):
            logging.info(f"Using a local installers repository: {os.environ['LOCAL_INSTALLERS']}")
            installers = f"file://{os.environ['LOCAL_INSTALLERS']}/"
            installers_index = f"{installers}/index.yml"
        else:
            logging.error(f"Local installers path does not exist: {os.environ['LOCAL_INSTALLERS']}")


# xdg data path
xdg_data_home = os.environ.get("XDG_DATA_HOME", f"{Path.home()}/.local/share")
class Paths:

    # Icon paths
    icons_user = f"{xdg_data_home}/icons"

    # Local paths
    base = f"{xdg_data_home}/bottles"

    # User applications path
    applications = f"{xdg_data_home}/applications/"

    temp = f"{base}/temp"
    runners = f"{base}/runners"
    bottles = f"{base}/bottles"
    layers = f"{base}/layers"
    dxvk = f"{base}/dxvk"
    vkd3d = f"{base}/vkd3d"
    nvapi = f"{base}/nvapi"
    data = f"{base}/data.yml"


class TrdyPaths:

    # External managers paths
    lutris = f"{xdg_data_home}*/Games"
    playonlinux = f"{xdg_data_home}/.PlayOnLinux/wineprefix/"
    bottlesv1 = f"{xdg_data_home}/.Bottles"


# Check if gamemode is available
gamemode_available = shutil.which("gamemoderun") or False
# Check if gamescope is available
gamescope_available = shutil.which("gamescope") or False

x_display = DisplayUtils.get_x_display()
