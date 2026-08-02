# lsfgvk.py
#
# Copyright 2026 Bottles Developers
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

import os
import webbrowser
from gettext import gettext as _

from gi.repository import Adw, Gio, GLib, Gtk

from bottles.backend.logger import Logger
from bottles.backend.utils.lsfgvk import (
    get_lsfg_vk_dll_path,
    remove_lsfg_vk_dll,
    store_lsfg_vk_dll,
)
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync

logging = Logger()


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-lsfg-vk.ui")
class LsfgVkDialog(Adw.Window):
    __gtype_name__ = "LsfgVkDialog"

    row_dll = Gtk.Template.Child()
    row_source = Gtk.Template.Child()
    btn_choose_dll = Gtk.Template.Child()
    btn_reset_dll = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    spin_multiplier = Gtk.Template.Child()
    spin_flow_scale = Gtk.Template.Child()
    switch_performance_mode = Gtk.Template.Child()

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        self.window = window
        self.manager = window.manager
        self.config = config
        self.bottle_path = ManagerUtils.get_bottle_path(config)
        self.dll_path = ""

        self.btn_choose_dll.connect("clicked", self.__choose_dll)
        self.btn_reset_dll.connect("clicked", self.__reset_dll)
        self.btn_save.connect("clicked", self.__save)
        self.row_source.connect("activated", self.__open_source)

        self.__update()

    def __update(self):
        parameters = self.config.Parameters
        dll = get_lsfg_vk_dll_path(self.bottle_path)
        self.__set_dll_path(dll if os.path.isfile(dll) else "")
        self.spin_multiplier.set_value(parameters.lsfg_vk_multiplier)
        self.spin_flow_scale.set_value(parameters.lsfg_vk_flow_scale)
        self.switch_performance_mode.set_active(parameters.lsfg_vk_performance_mode)

    def __set_dll_path(self, path):
        self.dll_path = path
        if path:
            self.row_dll.set_subtitle(path)
            self.btn_reset_dll.set_visible(True)
            return

        self.row_dll.set_subtitle(_("No DLL selected"))
        self.btn_reset_dll.set_visible(False)

    def __choose_dll(self, *_args):
        def set_path(dialog, result):
            try:
                file = dialog.open_finish(result)
                path = file.get_path() if file else None
                if not path:
                    self.window.show_toast(_("The selected file is unavailable."))
                    return
                self.__set_dll_path(path)
            except GLib.Error as error:
                if error.code != 2:
                    logging.warning("Error selecting Lossless.dll: %s" % error)

        dll_filter = Gtk.FileFilter()
        dll_filter.set_name(_("Windows libraries"))
        dll_filter.add_pattern("*.dll")
        dll_filter.add_pattern("*.DLL")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(dll_filter)

        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Select Lossless.dll"))
        dialog.set_modal(True)
        dialog.set_filters(filters)
        dialog.set_default_filter(dll_filter)
        dialog.open(parent=self, callback=set_path)

    def __reset_dll(self, *_args):
        self.__set_dll_path("")

    def __idle_save(self, *_args):
        if self.dll_path and not os.path.isfile(self.dll_path):
            self.window.show_toast(_("The selected DLL is no longer available."))
            return

        settings = {
            "lsfg_vk_multiplier": int(self.spin_multiplier.get_value()),
            "lsfg_vk_flow_scale": self.spin_flow_scale.get_value(),
            "lsfg_vk_performance_mode": self.switch_performance_mode.get_active(),
        }
        for key, value in settings.items():
            self.manager.update_config(
                config=self.config,
                key=key,
                value=value,
                scope="Parameters",
            )

        self.close()

    def __save(self, *_args):
        if not self.dll_path:
            self.btn_save.set_sensitive(False)
            RunAsync(
                remove_lsfg_vk_dll,
                callback=self.__dll_removed,
                bottle_path=self.bottle_path,
            )
            return

        self.btn_save.set_sensitive(False)
        RunAsync(
            store_lsfg_vk_dll,
            callback=self.__dll_stored,
            source=self.dll_path,
            bottle_path=self.bottle_path,
        )

    def __dll_removed(self, _result, error):
        self.btn_save.set_sensitive(True)
        if error:
            self.window.show_toast(_("The stored DLL could not be removed."))
            return
        GLib.idle_add(self.__idle_save)

    def __dll_stored(self, path, error):
        self.btn_save.set_sensitive(True)
        if error:
            self.window.show_toast(
                _(
                    "Select Lossless.dll from a legitimate Lossless Scaling "
                    "installation."
                )
            )
            return

        self.__set_dll_path(path)
        self.__idle_save()

    @staticmethod
    def __open_source(*_args):
        webbrowser.open_new_tab("https://github.com/PancakeTAS/lsfg-vk")
