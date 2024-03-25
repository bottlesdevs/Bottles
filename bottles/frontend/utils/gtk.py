# gtk.py
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

import re
from functools import wraps
from inspect import signature

from gi.repository import GLib


class GtkUtils:

    @staticmethod
    def validate_entry(entry, extend=None) -> bool:
        text = entry.get_text()
        if (
            re.search("[@!#$%^&*()<>?/|}{~:.;,'\"]", text)
            or len(text) == 0
            or text.isspace()
        ):
            entry.add_css_class("error")
            return False

        if extend is not None:
            if extend(text):
                entry.add_css_class("error")
                return False

        entry.remove_css_class("error")
        return True

    @staticmethod
    def run_in_main_loop(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _tmp = []
            if kwargs:
                for _, param in list(signature(func).parameters.items())[len(args) :]:
                    _tmp.append(
                        kwargs[param.name] if param.name in kwargs else param.default
                    )
                args = args + tuple(_tmp)
            return GLib.idle_add(func, *args)

        return wrapper
