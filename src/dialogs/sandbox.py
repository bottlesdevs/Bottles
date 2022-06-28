# sandbox.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
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

import re
from gi.repository import Gtk, GLib, Adw


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-sandbox.ui')
class SandboxDialog(Adw.Window):
    __gtype_name__ = 'SandboxDialog'

    # region Widgets
    switch_net = Gtk.Template.Child()
    switch_sound = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.__update(config)

        # connect signals
        self.switch_net.connect("state-set", self.__set_flag, "share_net")
        self.switch_sound.connect("state-set", self.__set_flag, "share_sound")

    def __set_flag(self, widget, state, flag):
        self.config = self.manager.update_config(
            config=self.config,
            key=flag,
            value=state,
            scope="Sandbox"
        ).data["config"]

    def __update(self, config):
        self.switch_net.set_active(config["Sandbox"]["share_net"])
        self.switch_sound.set_active(config["Sandbox"]["share_sound"])
