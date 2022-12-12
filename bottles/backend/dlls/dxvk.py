# dxvk.py
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


class DXVKComponent(DLLComponent):
    dlls = {
        "x32": [
            "d3d9.dll",
            "d3d10core.dll",
            "d3d11.dll",
            "dxgi.dll"
        ],
        "x64": [
            "d3d9.dll",
            "d3d10core.dll",
            "d3d11.dll",
            "dxgi.dll"
        ]
    }

    @staticmethod
    def get_base_path(version: str):
        return ManagerUtils.get_dxvk_path(version)
