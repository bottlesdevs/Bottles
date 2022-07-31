# vmtouch.py
#
# Copyright 2022 axtlos <axtlos@tar.black>
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
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gtk, GLib, Adw


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-vmtouch.ui')
class VmtouchDialog(Adw.Window):
    __gtype_name__ = 'VmtouchDialog'

    # region Widgets
    switch_cache_cwd = Gtk.Template.Child()
    arg_max_size = Gtk.Template.Child()
    switch_lock_all = Gtk.Template.Child()
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

        self.__update(config)

    def __update(self, config):
        parameters = config["Parameters"]
        self.switch_cache_cwd.set_state(parameters["vmtouch_cache_cwd"])
        self.arg_max_size.set_text(str(parameters["vmtouch_max_file_size"]))
        self.switch_lock_all.set_state(parameters["vmtouch_lock_memory"])

    def __idle_save(self, *_args):
        settings = {"vmtouch_cache_cwd": self.switch_cache_cwd.get_state(),
                    "vmtouch_max_file_size": int(self.arg_max_size.get_text()),
                    "vmtouch_lock_memory": self.switch_lock_all.get_state()}

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

