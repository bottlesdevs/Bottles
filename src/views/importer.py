# importer.py
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

from gettext import gettext as _
from gi.repository import Gtk, Adw

from bottles.dialogs.filechooser import FileChooser  # pyright: reportMissingImports=false

from bottles.backend.managers.backup import BackupManager
from bottles.utils.threading import RunAsync
from bottles.widgets.importer import ImporterEntry


@Gtk.Template(resource_path='/com/usebottles/bottles/importer.ui')
class ImporterView(Adw.Bin):
    __gtype_name__ = 'ImporterView'

    # region Widgets
    list_prefixes = Gtk.Template.Child()
    btn_find_prefixes = Gtk.Template.Child()
    btn_import_config = Gtk.Template.Child()
    btn_import_full = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    group_prefixes = Gtk.Template.Child()
    status_page = Gtk.Template.Child()

    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.import_manager = window.manager.import_manager

        # connect signals
        self.btn_back.connect("clicked", self.go_back)
        self.btn_find_prefixes.connect("clicked", self.__find_prefixes)
        self.btn_import_full.connect("clicked", self.__import_full_bck)
        self.btn_import_config.connect("clicked", self.__import_config_bck)

    def __find_prefixes(self, widget):
        """
        This function remove all entries from the list_prefixes, ask the
        manager to find all prefixes in the system and add them to the list
        """

        def update(result, error=False):
            widget.set_sensitive(True)
            if result.status:
                wineprefixes = result.data.get("wineprefixes")
                if len(wineprefixes) == 0:
                    return

                self.status_page.set_visible(False)
                self.group_prefixes.set_visible(True)

                while self.list_prefixes.get_first_child():
                    _w = self.list_prefixes.get_first_child()
                    self.list_prefixes.remove(_w)

                for prefix in result.data.get("wineprefixes"):
                    self.list_prefixes.append(ImporterEntry(self, prefix))

        widget.set_sensitive(False)

        RunAsync(
            self.import_manager.search_wineprefixes,
            callback=update
        )

    def __finish(self, result, error=False):
        if result.status:
            self.window.show_toast(_("Backup imported successfully."))
        else:
            self.window.show_toast(_("Import failed."))

    def __import_full_bck(self, *args):
        """
        This function show a dialog to the user, from which it can choose an
        archive backup to import into Bottles. It supports only .tar.gz files
        as Bottles export bottles in this format. Once selected, it will
        be imported.
        """
        def set_path(_dialog, response, _file_dialog):
            if response == -3:
                _file = _file_dialog.get_file()
                self.window.show_toast(_("Importing backup…"))
                RunAsync(
                    task_func=BackupManager.import_backup,
                    callback=self.__finish,
                    window=self.window,
                    scope="full",
                    path=_file.get_path(),
                    manager=self.manager
                )

        FileChooser(
            parent=self.window,
            title=_("Choose a backup archive"),
            action=Gtk.FileChooserAction.OPEN,
            buttons=(_("Cancel"), _("Import")),
            filters=["tar.gz"],
            callback=set_path
        )

    def __import_config_bck(self, *args):
        """
        This function show a dialog to the user, from which it can choose an
        archive backup to import into Bottles. It supports only .yml files
        which are the Bottles' configuration file. Once selected, it will
        be imported.
        """
        def set_path(_dialog, response, _file_dialog):
            if response == -3:
                _file = _file_dialog.get_file()
                self.window.show_toast(_("Importing backup…"))
                RunAsync(
                    task_func=BackupManager.import_backup,
                    callback=self.__finish,
                    window=self.window,
                    scope="config",
                    path=_file.get_path(),
                    manager=self.manager
                )

        FileChooser(
            parent=self.window,
            title=_("Choose a configuration file"),
            action=Gtk.FileChooserAction.OPEN,
            buttons=(_("Cancel"), _("Import")),
            filters=["yml"],
            callback=set_path
        )

    def go_back(self, *args):
        self.window.main_leaf.navigate(Adw.NavigationDirection.BACK)
