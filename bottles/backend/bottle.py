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

from typing import cast

from bottles.backend.models.config import BottleConfig


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

            local_bottles[local_bottle] = cast(BottleConfig, config_load.data)

        return local_bottles
