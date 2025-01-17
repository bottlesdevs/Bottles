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

from functools import wraps
from inspect import signature

from gi.repository import GLib, Gtk, GObject

from bottles.frontend.sh import ShUtils


class GtkUtils:
    @staticmethod
    def validate_entry(entry, extend=None) -> bool:
        var_assignment = entry.get_text()
        var_name = ShUtils.split_assignment(var_assignment)[0]
        if var_name and not ShUtils.is_name(var_name):
            GtkUtils.reset_entry_apply_button(entry)
            entry.add_css_class("error")
            return False

        if not var_name or "=" not in var_assignment:
            GtkUtils.reset_entry_apply_button(entry)
            entry.remove_css_class("error")
            return False

        if extend is not None:
            if not extend(var_name):
                GtkUtils.reset_entry_apply_button(entry)
                entry.add_css_class("error")
                return False

        entry.set_show_apply_button(True)
        entry.remove_css_class("error")
        return True

    @staticmethod
    def reset_entry_apply_button(entry) -> None:
        """
        Reset the apply_button within AdwEntryRow to hide it without disabling
        the functionality. This is needed because the widget does not provide
        an API to control when the button is displayed without disabling it
        """
        entry.set_show_apply_button(False)
        entry.set_show_apply_button(True)

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
    def get_parent_window() -> GObject.Object | None:
        """Retrieve the parent window from a widget."""
        toplevels = Gtk.Window.get_toplevels()
        return toplevels.get_item(0)
