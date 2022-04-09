# runner.py
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
from typing import NewType

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.backend.logger import Logger
from bottles.backend.globals import gamemode_available, gamescope_available, mangohud_available, obs_vkc_available
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.catalogs import win_versions
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.wine.wineserver import WineServer
from bottles.backend.wine.reg import Reg

logging = Logger()


class Runner:
    """
    This class handle everything related to the runner (e.g. WINE, Proton).
    It should not contain any manager logic (e.g. catalogs, checks, etc.) or
    any bottle related stuff (e.g. config handling, etc.), also DXVK, VKD3D,
    NVAPI handling should not performed from here. This class should be kept
    as clean as possible to easily migrate to the libwine in the future.
    <https://github.com/bottlesdevs/libwine>
    """

    @staticmethod
    def run_layer_executable(config: dict, layer: dict):
        """Run an executable in a layer."""
        WineExecutor(
            config=config,
            exec_path=layer["exec_path"],
            args=layer["exec_args"],
            environment=layer["exec_env"]
        ).run()

    @staticmethod
    def runner_update(config: dict, manager: object, runner: str):
        """
        This method should be executed after changing the runner
        for a bottle. It does a prefix update and re-initialize the
        active DLLComponents (dxvk, dxvk-nvapi, vkd3d…).
        """
        logging.info(f"Doing runner update for bottle: {config['Name']}", )
        wineboot = WineBoot(config)
        wineserver = WineServer(config)
        runner_path = ManagerUtils.get_runner_path(runner)

        if not os.path.exists(runner_path):
            logging.error(f"Runner {runner} not found in {runner_path}")
            return Result(
                status=False,
                data={"config": config}
            )

        # kill wineserver after update
        wineboot.kill()
        # wait for wineserver to go away
        wineserver.wait()
        # update bottle config
        new_config = manager.update_config(
            config=config,
            key="Runner",
            value=runner
        )
        # perform a prefix update
        wineboot.update()
        # re-initialize DLLComponents
        if config["Parameters"]["dxvk"]:
            manager.install_dll_component(config, "dxvk", overrides_only=True)
        if config["Parameters"]["dxvk_nvapi"]:
            manager.install_dll_component(config, "nvapi", overrides_only=True)
        if config["Parameters"]["vkd3d"]:
            manager.install_dll_component(config, "vkd3d", overrides_only=True)

        return Result(
            status=True,
            data={"config": new_config}
        )
