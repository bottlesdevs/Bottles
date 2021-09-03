# installer.py
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

from gi.repository import Gtk, GLib, Handy

from ..dialogs.generic import Dialog


@Gtk.Template(resource_path='/com/usebottles/bottles/installer-entry.ui')
class InstallerEntry(Handy.ActionRow):
    __gtype_name__ = 'InstallerEntry'

    # region Widgets
    btn_install = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    img_installed = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, installer, plain=False, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.installer = installer
        self.spinner = Gtk.Spinner()

        '''Populate widgets'''
        self.set_title(installer[0])
        self.set_subtitle(installer[1].get("Description"))

        # connect signals
        self.btn_install.connect('pressed', self.execute_installer)
        self.btn_manifest.connect('pressed', self.open_manifest)

    '''Open installer manifest'''

    def open_manifest(self, widget):
        dialog = Dialog(
            parent=self.window,
            title=_("Manifest for {0}").format(self.installer[0]),
            message=False,
            log=self.manager.installer_manager.get_installer(
                installer_name=self.installer[0],
                installer_category=self.installer[1]["Category"],
                plain=True
            )
        )
        dialog.run()
        dialog.destroy()

    '''Execute installer'''

    def execute_installer(self, widget):
        self.get_parent().set_sensitive(False)
        for w in widget.get_children():
            w.destroy()

        widget.set_sensitive(False)
        widget.add(self.spinner)

        self.spinner.show()
        GLib.idle_add(self.spinner.start)

        self.manager.installer_manager.install(
            config=self.config,
            installer=self.installer,
            widget=self
        )

    '''Set installed status'''

    def set_installed(self):
        self.spinner.stop()
        self.btn_install.set_visible(False)
        self.img_installed.set_visible(True)
        self.get_parent().set_sensitive(True)
