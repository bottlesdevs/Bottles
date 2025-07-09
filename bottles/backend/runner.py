# runner.py
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
from typing import TYPE_CHECKING

import logging
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.wineboot import WineBoot

if TYPE_CHECKING:
    from bottles.backend.managers.manager import Manager


class Runner:
    """
    This class handle everything related to the runner (e.g. Wine, Proton).
    It should not contain any manager logic (e.g. catalogs, checks, etc.) or
    any bottle related stuff (e.g. config handling, etc.), also DXVK, VKD3D,
    NVAPI handling should not performed from here.
    """

    @staticmethod
    def runner_update(
        config: BottleConfig, manager: "Manager", runner: str
    ) -> Result[dict]:
        """
        This method should be executed after changing the runner
        for a bottle. It does a prefix update and re-initialize the
        active DLLComponents (dxvk, dxvk-nvapi, vkd3d…) to re-create
        the overrides and fix broken registry keys.
        """
        logging.info(f"Doing runner update for bottle: {config.Name}")
        wineboot = WineBoot(config)

        if not runner.startswith("sys-"):
            runner_path = ManagerUtils.get_runner_path(runner)

            if not os.path.exists(runner_path):
                logging.error(f"Runner {runner} not found in {runner_path}")
                return Result(status=False, data={"config": config})

        # kill wineserver after update
        wineboot.kill(force_if_stalled=True)

        # update bottle config
        up_config = manager.update_config(
            config=config, key="Runner", value=runner
        ).data["config"]

        # perform a prefix update
        wineboot.update()

        # re-initialize DLLComponents
        if config.Parameters.dxvk:
            manager.install_dll_component(config, "dxvk", overrides_only=True)
        if config.Parameters.dxvk_nvapi:
            manager.install_dll_component(config, "nvapi", overrides_only=True)
        if config.Parameters.vkd3d:
            manager.install_dll_component(config, "vkd3d", overrides_only=True)

        return Result(status=True, data={"config": up_config})
