# vkbasalt.py
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

import os
from gi.repository import Gtk, GLib, Adw, Gdk
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.logger import Logger

logging = Logger()


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-fsr.ui')
class FsrDialog(Adw.Window):
    __gtype_name__ = 'FsrDialog'

    # Region Widgets
    btn_save = Gtk.Template.Child()
    combo_upscaling_resolution_mode = Gtk.Template.Child()
    str_list_upscaling_resolution_mode = Gtk.Template.Child()
    spin_sharpening_strength = Gtk.Template.Child()

    def __init__(self, parent_window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent_window)

        # Common variables and references
        self.window = parent_window
        self.manager = parent_window.manager
        self.config = config
        self.upscaling_resolution_mode = {
          False: _("Disabled"),
          "ultra": _("Ultra Quality"),
          "quality": _("Quality"),
          "balanced": _("Balanced"),
          "performance": _("Performance"),
        }

        # Connect signals
        self.btn_save.connect("clicked", self.__save)

        self.__update(config)

    def __update(self, config):
        parameters = config["Parameters"]

        # Populate entries
        for mode in self.upscaling_resolution_mode.values():
            self.str_list_upscaling_resolution_mode.append(mode)

        # Select right entry
        if parameters.get("fsr_upscaling_resolution_mode"):
            self.combo_upscaling_resolution_mode.set_selected(list(self.upscaling_resolution_mode.keys()).index(parameters.get("fsr_upscaling_resolution_mode")))

        self.spin_sharpening_strength.set_value(parameters.get("fsr_sharpening_strength"))

    def __idle_save(self, *_args):
        print(list(self.upscaling_resolution_mode.keys())[self.combo_upscaling_resolution_mode.get_selected()])
        settings = {"fsr_upscaling_resolution_mode": list(self.upscaling_resolution_mode.keys())[self.combo_upscaling_resolution_mode.get_selected()],
                    "fsr_sharpening_strength": int(self.spin_sharpening_strength.get_value())}

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

