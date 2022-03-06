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
from typing import Union


class SteamUtils:

    @staticmethod
    def parse_acf(data: str) -> Union[dict, None]:
        """
        Parse a steam app manifest file (.acf) into a dictionary with
        only AppID, Name, LastUpdated keys.
        TODO: need to be improved to parse all the keys
        """

        acf = {}

        for line in data.splitlines():
            line = line.strip()

            if "appid" in line:
                acf["AppID"] = line.split('"')[3]
            elif "name" in line:
                acf["Name"] = line.split('"')[3]
            elif "LastUpdated" in line:
                acf["LastUpdated"] = int(line.split('"')[3])

        if acf == {}:
            return None

        return acf
