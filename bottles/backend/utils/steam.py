# steam.py
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

import os, subprocess
from typing import Union, TextIO

from bottles.backend.models.vdict import VDFDict
from bottles.backend.utils import vdf


class SteamUtils:

    @staticmethod
    def parse_acf(data: str) -> VDFDict:
        """
        Parses aN ACF file. Just a wrapper for vdf.loads.
        """
        return vdf.loads(data)

    @staticmethod
    def parse_vdf(data: str) -> VDFDict:
        """
        Parses a VDF file. Just a wrapper for vdf.loads.
        """
        return vdf.loads(data)

    @staticmethod
    def to_vdf(data: VDFDict, fp: TextIO):
        """
        Saves a VDF file. Just a wrapper for vdf.dumps.
        """
        vdf.dump(data, fp, pretty=True)

    @staticmethod
    def is_proton(path: str) -> bool:
        """
        Checks if a directory is a Proton directory.
        """
        toolmanifest = os.path.join(path, f"toolmanifest.vdf")
        if not os.path.isfile(toolmanifest):
            return False

        f = open(toolmanifest, "r", errors="replace")
        data = SteamUtils.parse_vdf(f.read())
        compat_layer_name = data.get("manifest", {}) \
            .get("compatmanager_layer_name", {})

        commandline = data.get("manifest", {}) \
            .get("commandline", {})

        return "proton" in compat_layer_name or "proton" in commandline
