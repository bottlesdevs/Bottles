# vkd3d.py
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

from bottles.backend.dlls.dll import DLLComponent  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils


class VKD3DComponent(DLLComponent):
    dlls = {
        "x86": [
            "d3d12.dll"
        ],
        "x64": [
            "d3d12.dll"
        ]
    }

    def get_base_path(self, version: str):
        return ManagerUtils.get_vkd3d_path(version)
