# nvapi.py
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

from bottles.backend.dlls.dll import DLLComponent
from bottles.backend.utils.manager import ManagerUtils


class NVAPIComponent(DLLComponent):
    dlls = {
        "x32": [
            "nvapi.dll"
        ],
        "x64": [
            "nvapi64.dll"
        ],
        "/usr/lib64/nvidia/wine": [
            "nvngx.dll",
            "_nvngx.dll"
        ]
    }

    @staticmethod
    def get_base_path(version: str):
        return ManagerUtils.get_nvapi_path(version)
