# importer_view.py
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

from gettext import gettext as _

from gi.repository import Gtk, Adw

from bottles.backend.managers.backup import BackupManager
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.filters import add_yaml_filters, add_all_filters
from bottles.frontend.gtk import GtkUtils
from bottles.frontend.importer_row import ImporterRow


@Gtk.Template(resource_path="/com/usebottles/bottles/importer-view.ui")
class ImporterView(Adw.NavigationPage):
    __gtype_name__ = "ImporterView"

    # region Widgets
    list_prefixes = Gtk.Template.Child()
    btn_find_prefixes = Gtk.Template.Child()
    btn_import_config = Gtk.Template.Child()
    btn_import_full = Gtk.Template.Child()
    group_prefixes = Gtk.Template.Child()
    stack = Gtk.Template.Child()

    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.import_manager = window.manager.import_manager

        # connect signals
        self.btn_find_prefixes.connect("clicked", self.__find_prefixes)
        self.btn_import_full.connect("clicked", self.__import_full_bck)
        self.btn_import_config.connect("clicked", self.__import_config_bck)

        self.__find_prefixes()

    def __find_prefixes(self, *args):
        """
        This function remove all entries from the list_prefixes, ask the
        manager to find all prefixes in the system and add them to the list
        """

        @GtkUtils.run_in_main_loop
        def update(result, error=False):
            if result.ok:
                wineprefixes = result.data.get("wineprefixes")
                if len(wineprefixes) == 0:
                    self.stack.set_visible_child_name("empty-page")
                    return

                self.stack.set_visible_child_name("importer-page")

                while self.list_prefixes.get_first_child():
                    _w = self.list_prefixes.get_first_child()
                    self.list_prefixes.remove(_w)

                for prefix in result.data.get("wineprefixes"):
                    self.list_prefixes.append(ImporterRow(self, prefix))

        RunAsync(self.import_manager.search_wineprefixes, callback=update)

    @GtkUtils.run_in_main_loop
    def __finish(self, result, error=False):
        if result.ok:
            self.window.show_toast(_("Backup imported successfully"))
        else:
            self.window.show_toast(_("Import failed"))

    def __import_full_bck(self, *_args):
        """
        This function shows a dialog to the user, from which it can choose an
        archive backup to import into Bottles. It supports only .tar.gz files
        as Bottles export bottles in this format. Once selected, it will
        be imported.
        """

        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            self.window.show_toast(_("Importing backup…"))
            RunAsync(
                task_func=BackupManager.import_backup,
                callback=self.__finish,
                scope="full",
                path=dialog.get_file().get_path(),
            )

        dialog = Gtk.FileChooserNative.new(
            title=_("Select a Backup Archive"),
            action=Gtk.FileChooserAction.OPEN,
            parent=self.window,
            accept_label=_("Import"),
        )

        filter = Gtk.FileFilter()
        filter.set_name("GNU Gzip Archive")
        # TODO: Investigate why `filter.add_mime_type(...)` does not show filter in all distributions.
        # Intended MIME types are:
        #   - `application/gzip`
        filter.add_pattern("*.gz")

        dialog.add_filter(filter)
        add_all_filters(dialog)
        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def __import_config_bck(self, *_args):
        """
        This function shows a dialog to the user, from which it can choose an
        archive backup to import into Bottles. It supports only .yml files
        which are the Bottles' configuration file. Once selected, it will
        be imported.
        """

        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            self.window.show_toast(_("Importing backup…"))
            RunAsync(
                task_func=BackupManager.import_backup,
                callback=self.__finish,
                scope="config",
                path=dialog.get_file().get_path(),
            )

        dialog = Gtk.FileChooserNative.new(
            title=_("Select a Configuration File"),
            action=Gtk.FileChooserAction.OPEN,
            parent=self.window,
            accept_label=_("Import"),
        )

        add_yaml_filters(dialog)
        add_all_filters(dialog)
        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()
