# steam.py
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

import subprocess
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
