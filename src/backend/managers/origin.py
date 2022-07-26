# origin.py
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
# pylint: disable=import-error,missing-docstring

import os
import uuid
import json
from typing import Union, NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils


class OriginManager:

    @staticmethod
    def find_manifests_path(config: dict) -> Union[str, None]:
        """
        Finds the Origin manifests path.
        """
        paths = [
            os.path.join(
                ManagerUtils.get_bottle_path(config),
                "drive_c/ProgramData/Origin/LocalContent")
        ]

        for path in paths:
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def is_origin_supported(config: dict) -> bool:
        """
        Checks if Origin is supported.
        """
        return OriginManager.find_manifests_path(config) is not None

    @staticmethod
    def get_installed_games(config: dict) -> list:
        """
        Gets the games.
        """
        games = []
        return games
