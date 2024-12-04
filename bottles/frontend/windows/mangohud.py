# mangohud.py
#
# Copyright 2022 Bottles Contributors
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

from gi.repository import Gtk, GLib, Adw
from bottles.backend.logger import Logger

logging = Logger()


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-mangohud.ui")
class MangoHudDialog(Adw.Window):
    __gtype_name__ = "MangoHudDialog"

    # Region Widgets
    btn_save = Gtk.Template.Child()
    display_on_game_start = Gtk.Template.Child()

    def __init__(self, parent_window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent_window)

        # Common variables and references
        self.window = parent_window
        self.manager = parent_window.manager
        self.config = config

        # Connect signals
        self.btn_save.connect("clicked", self.__save)

        self.__update(config)

    def __update(self, config):
        parameters = config.Parameters
        self.display_on_game_start.set_active(parameters.mangohud_display_on_game_start)

    def __idle_save(self, *_args):
        settings = {
            "mangohud_display_on_game_start": self.display_on_game_start.get_active(),
        }

        for setting in settings.keys():
            self.manager.update_config(
                config=self.config,
                key=setting,
                value=settings[setting],
                scope="Parameters",
            )

            self.destroy()

    def __save(self, *_args):
        GLib.idle_add(self.__idle_save)
