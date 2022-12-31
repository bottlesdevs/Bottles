# gamescope.py
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
from gi.repository import Gtk, GLib, Adw
from bottles.backend.globals import Paths, vrr_available
from bottles.backend.utils.display import DisplayUtils


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-gamescope.ui')
class GamescopeDialog(Adw.Window):
    __gtype_name__ = 'GamescopeDialog'

    # region Widgets
    spin_width = Gtk.Template.Child()
    spin_height = Gtk.Template.Child()
    spin_gamescope_width = Gtk.Template.Child()
    spin_gamescope_height = Gtk.Template.Child()
    spin_fps_limit = Gtk.Template.Child()
    spin_fps_limit_no_focus = Gtk.Template.Child()
    row_vrr = Gtk.Template.Child()
    switch_vrr = Gtk.Template.Child()
    switch_scaling = Gtk.Template.Child()
    toggle_borderless = Gtk.Template.Child()
    toggle_fullscreen = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        # connect signals
        self.btn_save.connect("clicked", self.__save)
        self.toggle_borderless.connect("toggled", self.__change_wtype, "b")
        self.toggle_fullscreen.connect("toggled", self.__change_wtype, "f")

        self.__update(config)

        # Set VRR row to visible if the compositor supports VRR
        if vrr_available:
            self.row_vrr.set_visible(True)

            if DisplayUtils.display_server_type() == "wayland":
                warning = _("This feature depends on the version of the compositor.")
                learn_more = _("Learn more about variable refresh rate")
                link = f"<a href=\"https://wiki.archlinux.org/title/Variable_refresh_rate#Wayland_configuration\">{learn_more}</a>"
                message = f"{self.row_vrr.get_subtitle()} {warning} {link}"
                self.row_vrr.set_subtitle(message)

    def __change_wtype(self, widget, wtype):
        self.toggle_borderless.handler_block_by_func(self.__change_wtype)
        self.toggle_fullscreen.handler_block_by_func(self.__change_wtype)
        if wtype == "b":
            self.toggle_fullscreen.set_active(False)
            self.toggle_borderless.set_active(True)
        elif wtype == "f":
            self.toggle_fullscreen.set_active(True)
            self.toggle_borderless.set_active(False)

        self.toggle_borderless.handler_unblock_by_func(self.__change_wtype)
        self.toggle_fullscreen.handler_unblock_by_func(self.__change_wtype)

    def __update(self, config):
        self.toggle_borderless.handler_block_by_func(self.__change_wtype)
        self.toggle_fullscreen.handler_block_by_func(self.__change_wtype)

        parameters = config["Parameters"]
        self.spin_width.set_value(parameters.get("gamescope_game_width"))
        self.spin_height.set_value(parameters.get("gamescope_game_height"))
        self.spin_gamescope_width.set_value(parameters.get("gamescope_window_width"))
        self.spin_gamescope_height.set_value(parameters.get("gamescope_window_height"))
        self.spin_fps_limit.set_value(parameters.get("gamescope_fps"))
        self.spin_fps_limit_no_focus.set_value(parameters.get("gamescope_fps_no_focus"))
        self.switch_scaling.set_state(parameters.get("gamescope_scaling"))
        self.switch_vrr.set_active(parameters.get("gamescope_vrr"))
        self.toggle_borderless.set_active(parameters.get("gamescope_borderless"))
        self.toggle_fullscreen.set_active(parameters.get("gamescope_fullscreen"))

        self.toggle_borderless.handler_unblock_by_func(self.__change_wtype)
        self.toggle_fullscreen.handler_unblock_by_func(self.__change_wtype)

    def __idle_save(self, *_args):
        settings = {"gamescope_game_width": self.spin_width.get_value(),
                    "gamescope_game_height": self.spin_height.get_value(),
                    "gamescope_window_width": self.spin_gamescope_width.get_value(),
                    "gamescope_window_height": self.spin_gamescope_height.get_value(),
                    "gamescope_fps": self.spin_fps_limit.get_value(),
                    "gamescope_fps_no_focus": self.spin_fps_limit_no_focus.get_value(),
                    "gamescope_scaling": self.switch_scaling.get_state(),
                    "gamescope_vrr": self.switch_vrr.get_active(),
                    "gamescope_borderless": self.toggle_borderless.get_active(),
                    "gamescope_fullscreen": self.toggle_fullscreen.get_active()}

        for setting in settings.keys():
            self.manager.update_config(
                config=self.config,
                key=setting,
                value=settings[setting],
                scope="Parameters"
            )

        self.destroy()

    def __save(self, *_args):
        GLib.idle_add(self.__idle_save)

