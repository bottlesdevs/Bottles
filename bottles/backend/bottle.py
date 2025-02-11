# bottle.py
#
# Copyright 2025 The Bottles Contributors
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

import os
import yaml
from dataclasses import dataclass

from bottles.backend.typing import WindowsAPI, VersionedComponent, Environment
from bottles.backend.models.config import BottleConfig


# BottleConfig(Name='d', Arch='win64', Windows='win10', Runner='sys-wine-10.0', WorkingDir='', DXVK='', NVAPI='', VKD3D='', LatencyFleX='', Path='d', Custom_Path=False, Environment='Application', Creation_Date='', Update_Date='', Versioning=False, Versioning_Exclusion_Patterns=[], State=0, Parameters=BottleParams(dxvk=False, dxvk_nvapi=False, vkd3d=False, latencyflex=False, mangohud=False, mangohud_display_on_game_start=True, obsvkc=False, vkbasalt=False, gamemode=False, gamescope=False, gamescope_game_width=0, gamescope_game_height=0, gamescope_window_width=0, gamescope_window_height=0, gamescope_fps=0, gamescope_fps_no_focus=0, gamescope_scaling=False, gamescope_borderless=False, gamescope_fullscreen=True, sync='wine', fsr=False, fsr_sharpening_strength=2, fsr_quality_mode='none', custom_dpi=96, renderer='gl', discrete_gpu=False, virtual_desktop=False, virtual_desktop_res='1280x720', pulseaudio_latency=False, fullscreen_capture=False, take_focus=False, mouse_warp=True, decorated=True, fixme_logs=False, use_runtime=False, use_eac_runtime=True, use_be_runtime=True, use_steam_runtime=False, sandbox=False, versioning_compression=False, versioning_automatic=False, versioning_exclusion_patterns=False, vmtouch=False, vmtouch_cache_cwd=False), Sandbox=BottleSandboxParams(share_net=False, share_sound=False), Environment_Variables={}, Installed_Dependencies=[], DLL_Overrides={}, External_Programs={}, Uninstallers={}, session_arguments='', run_in_terminal=False, Language='sys', CompatData='', data={}, RunnerPath='')
@dataclass
class BottleClass:
    name: str
    runner: str
    environment: Environment
    mangohud: bool = False
    vkbasalt: bool = False
    gamemode: bool = False
    gamescope: bool = False
    fidelityfx_super_resolution: bool = False
    dxvk: VersionedComponent = False
    nvapi: VersionedComponent = False
    vkd3d: VersionedComponent = False
    latencyflex: VersionedComponent = False
    architecture: WindowsAPI = WindowsAPI.WIN64


class Bottle:
    """Class representing a bottle."""

    @staticmethod
    def generate_local_bottles_list(bottles_dir: str) -> dict[str, BottleConfig]:
        """Generate a list of local bottles."""

        local_bottles = {}
        local_bottles_list = os.listdir(bottles_dir)

        for local_bottle in local_bottles_list:
            local_bottle_dir = os.path.join(bottles_dir, local_bottle)
            bottle_config_file_path = os.path.join(local_bottle_dir, "bottle.yml")
            placeholder_file_path = os.path.join(local_bottle_dir, "placeholder.yml")

            try:
                with open(placeholder_file_path) as file:
                    configuration = yaml.safe_load(file)
                    bottle_config_file_path = configuration["Path"]
            except FileNotFoundError:
                pass

            if not os.path.isfile(bottle_config_file_path):
                continue

            config_load = BottleConfig.load(bottle_config_file_path)

            if not config_load.status:
                raise TypeError(f"Unable to load {bottle_config_file_path}")

            local_bottles[local_bottle] = config_load.data

        return local_bottles
