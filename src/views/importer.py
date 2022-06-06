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

from bottles.backend.managers.backup import BackupManager  # pyright: reportMissingImports=false
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
                    self.list_prefixes.append(ImporterEntry(self.window, prefix))

        widget.set_sensitive(False)

        RunAsync(
            self.import_manager.search_wineprefixes,
            callback=update
        )

    def __import_full_bck(self, widget):
        """
        This function show a dialog to the user, from which it can choose an
        archive backup to import into Bottles. It support only .tar.gz files
        as Bottles export bottles in this format. Once selected, it will
        be imported.
        TODO: remove .run
        """
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose a backup archive"),
            self.window,
            Gtk.FileChooserAction.OPEN
        )

        filter_tar = Gtk.FileFilter()
        filter_tar.set_name(".tar.gz")
        filter_tar.add_pattern("*.tar.gz")
        file_dialog.add_filter(filter_tar)

        response = file_dialog.run()

        if response == -3:
            RunAsync(
                task_func=BackupManager.import_backup,
                window=self.window,
                scope="full",
                path=file_dialog.get_filename(),
                manager=self.manager
            )

        file_dialog.destroy()

    def __import_config_bck(self, widget):
        """
        This function show a dialog to the user, from which it can choose an
        archive backup to import into Bottles. It support only .yml files
        which are the Bottles configuration file. Once selected, it will
        be imported.
        TODO: remove .run
        """
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose a configuration file"),
            self.window,
            Gtk.FileChooserAction.OPEN
        )

        filter_yml = Gtk.FileFilter()
        filter_yml.set_name(".yml")
        filter_yml.add_pattern("*.yml")
        file_dialog.add_filter(filter_yml)

        response = file_dialog.run()

        if response == -3:
            RunAsync(
                task_func=BackupManager.import_backup,
                window=self.window,
                scope="config",
                path=file_dialog.get_filename(),
                manager=self.manager
            )

        file_dialog.destroy()


    def go_back(self, widget=False):
        self.window.main_leaf.navigate(Adw.NavigationDirection.BACK)