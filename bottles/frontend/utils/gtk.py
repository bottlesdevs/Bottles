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

from typing import Optional
from functools import wraps
from inspect import signature

from gi.repository import GLib, Gtk

from bottles.frontend.utils.sh import ShUtils


class GtkUtils:
    @staticmethod
    def validate_entry(entry, extend=None) -> bool:
        var_assignment = entry.get_text()
        var_name = ShUtils.split_assignment(var_assignment)[0]
        if "=" not in var_assignment or not ShUtils.is_name(var_name):
            entry.add_css_class("error")
            return False

        if extend is not None:
            if not extend(var_name):
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

    @staticmethod
    def get_parent_window() -> Optional[Gtk.Widget]:
        """Retrieve the parent window from a widget."""
        toplevels = Gtk.Window.get_toplevels()
        return toplevels.get_item(0)
