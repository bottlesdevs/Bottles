# gtk.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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
from typing import Optional

from gi.repository import Gdk, GLib, GObject, Gtk

from bottles.frontend.utils.sh import ShUtils


FONT_SCALE_VALUES = (1.0, 1.1, 1.25, 1.5, 1.75, 2.0)


class FontScaleManager:
    DEFAULT_DPI = 96 * 1024

    def __init__(self, settings, gtk_settings=None, display=None):
        self.settings = settings
        self.gtk_settings = gtk_settings or Gtk.Settings.get_default()
        self.display = display or Gdk.Display.get_default()
        self._updating = False

        if self.gtk_settings is None:
            return

        self.settings.connect("changed::font-scale", self._apply)
        if self.display is not None:
            self.display.connect_after(
                "setting-changed", self._on_system_setting_changed
            )
        self._apply()

    def _get_current_dpi(self):
        dpi = self.gtk_settings.get_property("gtk-xft-dpi")
        return dpi if dpi > 0 else self.DEFAULT_DPI

    def _apply(self, *_args):
        if self._updating:
            return

        self._updating = True
        try:
            self.gtk_settings.reset_property("gtk-xft-dpi")
            scale = self.settings.get_double("font-scale")
            scale = min(FONT_SCALE_VALUES, key=lambda value: abs(value - scale))
            if self.settings.get_double("font-scale") != scale:
                self.settings.set_double("font-scale", scale)

            if scale == 1.0:
                return

            target_dpi = round(self._get_current_dpi() * scale)
            self.gtk_settings.set_property("gtk-xft-dpi", target_dpi)
        finally:
            self._updating = False

    def _on_system_setting_changed(self, _display, setting):
        if setting == "gtk-xft-dpi":
            self._apply()


class GtkUtils:
    @staticmethod
    def create_full_width_string_list_factory() -> Gtk.SignalListItemFactory:
        factory = Gtk.SignalListItemFactory()

        def setup(_factory, list_item):
            list_item.set_child(Gtk.Label(xalign=0))

        def bind(_factory, list_item):
            list_item.get_child().set_label(list_item.get_item().get_string())

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        return factory

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
    def validate_env_var_name(entry, extend=None) -> bool:
        var_assignment = entry.get_text()
        if var_assignment and not ShUtils.is_name(var_assignment):
            GtkUtils.reset_entry_apply_button(entry)
            entry.add_css_class("error")
            return False

        if not var_assignment:
            GtkUtils.reset_entry_apply_button(entry)
            entry.remove_css_class("error")
            return False

        if extend is not None:
            if not extend(var_assignment):
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
    def get_parent_window() -> Optional[GObject.Object]:
        """Retrieve the parent window from a widget."""
        toplevels = Gtk.Window.get_toplevels()
        return toplevels.get_item(0)
