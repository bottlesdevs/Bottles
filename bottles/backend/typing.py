# typing.py
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

from typing import Literal
from enum import Enum

type VersionedComponent = str | Literal[False]


class WindowsAPI(Enum):
    WIN64 = "Win64"
    WIN32 = "Win32"
    WIN16 = "Win16"


class Environment(Enum):
    APPLICATION = "Application"
    GAMING = "Gaming"
    CUSTOM = "Custom"
