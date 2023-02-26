# result.py
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
from typing import TypeVar, Generic

T = TypeVar('T')


class Result(Generic[T]):
    """
    The Result object is the standard return object for every
    method in the backend. It is important to use this object
    to keep the code clean and consistent.
    """

    status: bool = False
    data: T = None
    message: str = ""

    def __init__(
            self,
            status: bool = False,
            data: T = None,
            message: str = ""
    ):
        self.status = status
        self.data = data
        self.message = message

    def set_status(self, v: bool):
        self.status = v
