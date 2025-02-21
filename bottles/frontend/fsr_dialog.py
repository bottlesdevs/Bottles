# fsr_dialog.py
#
# Copyright 2025 The Bottles Contributors
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

from gettext import gettext as _

from gi.repository import Gtk, GLib, Adw


@Gtk.Template(resource_path="/com/usebottles/bottles/fsr-dialog.ui")
class FsrDialog(Adw.Window):
    __gtype_name__ = "FsrDialog"

    # Region Widgets
    btn_save = Gtk.Template.Child()
    combo_quality_mode = Gtk.Template.Child()
    str_list_quality_mode = Gtk.Template.Child()
    spin_sharpening_strength = Gtk.Template.Child()

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # Common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.quality_mode = {
            "none": _("None"),
            "ultra": _("Ultra Quality"),
            "quality": _("Quality"),
            "balanced": _("Balanced"),
            "performance": _("Performance"),
        }

        # Connect signals
        self.btn_save.connect("clicked", self.__save)

        self.__update(config)

    def __update(self, config):
        parameters = config.Parameters

        # Populate entries
        for mode in self.quality_mode.values():
            self.str_list_quality_mode.append(mode)

        # Select right entry
        if parameters.fsr_quality_mode:
            self.combo_quality_mode.set_selected(
                list(self.quality_mode.keys()).index(parameters.fsr_quality_mode)
            )

        self.spin_sharpening_strength.set_value(parameters.fsr_sharpening_strength)

    def __idle_save(self, *_args):
        print(list(self.quality_mode.keys())[self.combo_quality_mode.get_selected()])
        settings = {
            "fsr_quality_mode": list(self.quality_mode.keys())[
                self.combo_quality_mode.get_selected()
            ],
            "fsr_sharpening_strength": int(self.spin_sharpening_strength.get_value()),
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
