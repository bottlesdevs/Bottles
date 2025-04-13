# dependency_entry_row.py
#
# Copyright 2025 The Bottles Contributors
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

import contextlib
import webbrowser
from gettext import gettext as _

from gi.repository import Gtk, Adw

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.gtk import GtkUtils
from bottles.frontend.generic import SourceDialog


@Gtk.Template(resource_path="/com/usebottles/bottles/dependency-entry-row.ui")
class DependencyEntryRow(Adw.ActionRow):
    __gtype_name__ = "DependencyEntryRow"

    # region Widgets
    label_category = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_reinstall = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    btn_license = Gtk.Template.Child()
    btn_err = Gtk.Template.Child()
    box_actions = Gtk.Template.Child()
    spinner = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config: BottleConfig, dependency, plain=False, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.dependency = dependency

        if plain:
            """
            If the dependency is plain, treat it as a placeholder, it
            can be used to display "fake" elements on the list
            """
            self.set_title(dependency)
            self.set_subtitle("")
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(False)
            self.btn_reinstall.set_visible(True)
            return

        if self.config.Arch not in dependency[1].get("Arch", "win64_win32"):
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(False)
            self.btn_reinstall.set_visible(False)
            self.btn_err.set_visible(True)
            self.btn_err.set_tooltip_text(
                _("This dependency is not compatible with this bottle architecture.")
            )

        # populate widgets
        self.set_title(dependency[0])
        self.set_subtitle(dependency[1].get("Description"))
        self.label_category.set_text(dependency[1].get("Category"))

        # connect signals
        self.btn_install.connect("clicked", self.install_dependency)
        self.btn_reinstall.connect("clicked", self.install_dependency)
        self.btn_remove.connect("clicked", self.remove_dependency)
        self.btn_manifest.connect("clicked", self.open_manifest)
        self.btn_license.connect("clicked", self.open_license)

        if dependency[0] in self.config.Installed_Dependencies:
            """
            If the dependency is installed, hide the btn_install
            button and show the btn_remove button
            """
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(True)
            self.btn_reinstall.set_visible(True)

        if dependency[0] in self.config.Uninstallers.keys():
            """
            If the dependency has no uninstaller, disable the
            btn_remove button
            """
            uninstaller = self.config.Uninstallers[dependency[0]]
            if uninstaller in [False, "NO_UNINSTALLER"]:
                self.btn_remove.set_sensitive(False)

    def open_manifest(self, _widget):
        """
        This function pop up a dialog with the manifest
        of the dependency
        """
        SourceDialog(
            parent=self.window,
            title=_("Manifest for {0}").format(self.dependency[0]),
            message=self.manager.dependency_manager.get_dependency(
                name=self.dependency[0], plain=True
            ),
        ).present()

    def open_license(self, _widget):
        """
        This function pop up a dialog with the license
        of the dependency
        """
        manifest = self.manager.dependency_manager.get_dependency(
            name=self.dependency[0]
        )
        webbrowser.open(manifest["License_url"])

    def install_dependency(self, _widget):
        """
        This function install the dependency in the bottle, it
        will also prevent user from installing other dependencies
        during the installation process, will show a spinner
        and set the dependency as installed in the bottle
        configuration
        """
        self.get_parent().set_sensitive(False)
        self.btn_install.set_visible(False)
        self.spinner.show()
        self.spinner.start()

        RunAsync(
            task_func=self.manager.dependency_manager.install,
            callback=self.set_install_status,
            config=self.config,
            dependency=self.dependency,
        )

    def remove_dependency(self, _widget):
        """
        This function remove the dependency from the bottle
        configuration
        """
        _widget.set_sensitive(False)
        RunAsync(
            task_func=self.manager.remove_dependency,
            callback=self.set_install_status,
            config=self.config,
            dependency=self.dependency,
        )

    @GtkUtils.run_in_main_loop
    def set_install_status(self, result: Result, error=None):
        """
        This function set the dependency as installed
        if the installation is successful, or uninstalled
        if the uninstallation is successful.
        """
        if result is not None and result.status:
            if self.config.Parameters.versioning_automatic:
                self.window.page_details.view_versioning.update()
            uninstaller = result.data.get("uninstaller")
            removed = result.data.get("removed") or False
            if removed:
                self.window.show_toast(
                    _('"{0}" uninstalled').format(self.dependency[0])
                )
            else:
                self.window.show_toast(_('"{0}" installed').format(self.dependency[0]))
            self.set_installed(uninstaller, removed)
            return
        self.set_err()

    def set_err(self):
        """
        This function set the dependency as not installed
        if errors occur during installation
        """
        self.spinner.stop()
        self.btn_install.set_visible(False)
        self.btn_remove.set_visible(False)
        self.btn_err.set_visible(True)
        self.get_parent().set_sensitive(True)
        self.window.show_toast(_('"{0}" failed to install').format(self.dependency[0]))

    def set_installed(self, installer=True, removed=False):
        """
        This function set the dependency as installed
        """
        self.spinner.stop()
        if not removed:
            self.btn_install.set_visible(False)
            if installer:
                self.btn_remove.set_visible(True)
                self.btn_remove.set_sensitive(True)
        else:
            self.btn_remove.set_visible(False)
            self.btn_install.set_visible(True)

        self.btn_reinstall.set_sensitive(True)

        with contextlib.suppress(AttributeError):
            self.get_parent().set_sensitive(True)
