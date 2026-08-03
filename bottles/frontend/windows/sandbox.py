# sandbox.py
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

from gettext import gettext as _

from gi.repository import Adw, Gtk

from bottles.backend.managers.sandbox import SandboxManager


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-sandbox.ui")
class SandboxDialog(Adw.Window):
    __gtype_name__ = "SandboxDialog"

    # region Widgets
    switch_net = Gtk.Template.Child()
    switch_sound = Gtk.Template.Child()
    row_input = Gtk.Template.Child()
    switch_input = Gtk.Template.Child()
    row_usb = Gtk.Template.Child()
    switch_usb = Gtk.Template.Child()

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
        self.switch_input.connect("state-set", self.__set_flag, "share_input")
        self.switch_usb.connect("state-set", self.__set_flag, "share_usb")

    def __set_flag(self, widget, state, flag):
        self.config = self.manager.update_config(
            config=self.config, key=flag, value=state, scope="Sandbox"
        ).data["config"]

    def __update(self, config):
        self.switch_net.set_active(config.Sandbox.share_net)
        self.switch_sound.set_active(config.Sandbox.share_sound)
        self.switch_input.set_active(config.Sandbox.share_input)
        self.switch_usb.set_active(config.Sandbox.share_usb)
        if not SandboxManager.supports_input_devices():
            self.row_input.set_sensitive(False)
            self.row_input.set_subtitle(
                _("Input devices cannot be shared on this system.")
            )
        if not SandboxManager.supports_usb_devices():
            self.row_usb.set_sensitive(False)
            self.row_usb.set_subtitle(_("USB devices cannot be shared on this system."))
