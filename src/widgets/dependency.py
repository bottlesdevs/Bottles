# dependency.py
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

import webbrowser
from gi.repository import Gtk, GLib, Handy
from gettext import gettext as _
from ..utils import RunAsync
from ..dialogs.generic import Dialog


@Gtk.Template(resource_path='/com/usebottles/bottles/dependency-entry.ui')
class DependencyEntry(Handy.ActionRow):
    __gtype_name__ = 'DependencyEntry'

    # region Widgets
    label_category = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    btn_license = Gtk.Template.Child()
    btn_err = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, dependency, plain=False, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.dependency = dependency
        self.spinner = Gtk.Spinner()

        if plain:
            '''
            If the dependency is plain, treat it as a placeholder, it
            can be used to display "fake" elements on the list
            '''
            self.set_title(dependency)
            self.set_subtitle("")
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(False)
            return None

        # populate widgets
        self.set_title(dependency[0])
        self.set_subtitle(dependency[1].get("Description"))
        self.label_category.set_text(dependency[1].get("Category"))

        # connect signals
        self.btn_install.connect('pressed', self.install_dependency)
        self.btn_remove.connect('pressed', self.remove_dependency)
        self.btn_manifest.connect('pressed', self.open_manifest)
        self.btn_license.connect('pressed', self.open_license)

        if dependency[0] in self.config.get("Installed_Dependencies"):
            '''
            If the dependency is installed, hide the btn_install
            button and show the btn_remove button
            '''
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(True)

        if dependency[0] in self.config.get("Uninstallers").keys():
            '''
            If the dependency has no uninstaller, disable the
            btn_remove button
            '''
            print("si")
            if self.config["Uninstallers"][dependency[0]] == "NO_UNINSTALLER":
                self.btn_remove.set_sensitive(False)

    def open_manifest(self, widget):
        '''
        This function pop up a dialog with the manifest
        of the dependency
        '''
        dialog = Dialog(
            parent=self.window,
            title=_("Manifest for {0}").format(self.dependency[0]),
            message=False,
            log=self.manager.dependency_manager.get_dependency(
                dependency_name=self.dependency[0],
                dependency_category=self.dependency[1]["Category"],
                plain=True
            )
        )
        dialog.run()
        dialog.destroy()

    def open_license(self, widget):
        '''
        This function pop up a dialog with the license
        of the dependency
        '''
        manifest = self.manager.dependency_manager.get_dependency(
            dependency_name=self.dependency[0],
            dependency_category=self.dependency[1]["Category"]
        )
        webbrowser.open(manifest["License_url"])

    def install_dependency(self, widget):
        '''
        This function install the dependency in the bottle, it
        will also prevent user from installing other dependencies
        during the installation process, will show a spinner
        and set the dependency as installed in the bottle
        configuration
        '''
        self.get_parent().set_sensitive(False)
        for w in widget.get_children():
            w.destroy()

        widget.set_sensitive(False)
        widget.add(self.spinner)

        self.spinner.show()
        GLib.idle_add(self.spinner.start)

        RunAsync(
            self.manager.dependency_manager.install, None,
            config=self.config,
            dependency=self.dependency,
            widget=self
        )

    def remove_dependency(self, widget):
        '''
        This function remove the dependency from the bottle
        configuration
        '''
        GLib.idle_add(widget.set_sensitive, False)
        self.manager.remove_dependency(
            config=self.config,
            dependency=self.dependency,
            widget=self
        )

    def set_err(self):
        '''
        This function set the dependency as not installed
        if errors occur during installation
        '''
        self.spinner.stop()
        self.btn_install.set_visible(False)
        self.btn_remove.set_visible(False)
        self.btn_err.set_visible(True)

    def set_installed(self, has_installer=True):
        '''
        This function set the dependency as installed
        '''
        self.spinner.stop()
        self.btn_install.set_visible(False)
        if has_installer:
            self.btn_remove.set_visible(True)
            self.btn_remove.set_sensitive(True)

        self.get_parent().set_sensitive(True)
