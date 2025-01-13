# sh.py
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
#

import re

_is_name = re.compile(r"""[_a-zA-Z][_a-zA-Z0-9]*""")


class ShUtils:
    @staticmethod
    def is_name(text: str) -> bool:
        return bool(_is_name.fullmatch(text))

    @staticmethod
    def split_assignment(text: str) -> tuple[str, str]:
        name, _, value = text.partition("=")
        return (name, value)
