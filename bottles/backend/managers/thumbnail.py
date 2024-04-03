# thumbnail.py
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

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


class ThumbnailManager:

    @staticmethod
    def get_path(config: BottleConfig, uri: str):
        if uri.startswith("grid:"):
            return ThumbnailManager.__load_grid(config, uri)
        # elif uri.startswith("epic:"):
        #     return ThumbnailManager.__load_epic(config, uri)
        # elif uri.startswith("origin:"):
        #     return ThumbnailManager.__load_origin(config, uri)
        logging.error("Unknown URI: " + uri)
        return None

    @staticmethod
    def __load_grid(config: BottleConfig, uri: str):
        bottle_path = ManagerUtils.get_bottle_path(config)
        file_name = uri[5:]
        path = os.path.join(bottle_path, "grids", file_name)

        if not os.path.exists(path):
            logging.error("Grid not found: " + path)
            return None

        return path
