import os
import shutil
from pathlib import Path


class BottlesRepositories:
    components = "https://raw.githubusercontent.com/bottlesdevs/components/main/"
    components_index = f"{components}/index.yml"

    dependencies = "https://raw.githubusercontent.com/bottlesdevs/dependencies/main/"
    dependencies_index = f"{dependencies}/index.yml"

    installers = "https://raw.githubusercontent.com/bottlesdevs/programs/main/"
    installers_index = f"{installers}/index.yml"

    if "TESTING_REPOS" in os.environ:
        if int(os.environ["TESTING_REPOS"]) == 1:
            dependencies_index = f"{dependencies}/testing.yml"
            components_index = f"{components}/testing.yml"


class BottlesPaths:

    # Icon paths
    icons_user = f"{Path.home()}/.local/share/icons"

    # Local paths
    base = f"{Path.home()}/.local/share/bottles"

    if "IS_FLATPAK" in os.environ:
        base_n = base
        base = f"{Path.home()}/.var/app/{os.environ['FLATPAK_ID']}/data/bottles"

    temp = f"{base}/temp"
    runners = f"{base}/runners"
    bottles = f"{base}/bottles"
    dxvk = f"{base}/dxvk"
    vkd3d = f"{base}/vkd3d"


class TrdyPaths:

    # External managers paths
    lutris = f"{Path.home()}*/Games"
    playonlinux = f"{Path.home()}/.PlayOnLinux/wineprefix/"
    bottlesv1 = f"{Path.home()}/.Bottles"


# Check if gamemode is available
gamemode_available = False
if shutil.which("gamemoderun") is not None:
    gamemode_available = True
