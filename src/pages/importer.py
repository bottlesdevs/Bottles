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

from gi.repository import Gtk

@Gtk.Template(resource_path='/com/usebottles/bottles/importer-entry.ui')
class BottlesImporterEntry(Gtk.Box):
    __gtype_name__ = 'BottlesImporterEntry'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    label_name = Gtk.Template.Child()
    label_manager = Gtk.Template.Child()
    btn_import = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    img_lock = Gtk.Template.Child()

    def __init__(self, window, prefix, sample=False, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Set reusable variables
        '''
        self.window = window
        self.runner = window.runner
        self.prefix = prefix

        '''
        Populate widgets with data
        '''
        if not sample:
            self.label_name.set_text(prefix.get("Name"))
            self.label_manager.set_text(prefix.get("Manager"))
            if prefix.get("Lock"):
                self.img_lock.set_visible(True)
        else:
            self.label_name.set_text("I haven't found any wineprefixes to import.")
            for w in [self.label_manager,
                      self.btn_browse,
                      self.btn_import]:
                w.set_visible(False)

        '''
        Connect widgets to signals
        '''
        self.btn_browse.connect("pressed", self.browse_wineprefix)
        self.btn_import.connect("pressed", self.import_wineprefix)

    def browse_wineprefix(self, widget):
        self.runner.browse_wineprefix(self.prefix)

    def import_wineprefix(self, widget):
        if self.runner.import_wineprefix(self.prefix, widget):
            self.destroy()


@Gtk.Template(resource_path='/com/usebottles/bottles/importer.ui')
class BottlesImporter(Gtk.ScrolledWindow):
    __gtype_name__ = 'BottlesImporter'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    list_prefixes = Gtk.Template.Child()
    btn_search_wineprefixes = Gtk.Template.Child()
    btn_import_configuration = Gtk.Template.Child()
    btn_import_full = Gtk.Template.Child()

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Set reusable variables
        '''
        self.window = window
        self.runner = window.runner

        '''
        Connect widgets to signals
        '''
        self.btn_search_wineprefixes.connect("pressed", self.search_wineprefixes)
        self.btn_import_full.connect("pressed", self.import_backup_full)

    def search_wineprefixes(self, widget):
        '''
        Destroy all childs in list_prefixes
        '''
        for w in self.list_prefixes.get_children():
            w.destroy()

        '''
        Get and list wineprefixes from other managers
        '''
        wineprefixes = self.runner.search_wineprefixes()

        if len(wineprefixes) > 0:
            for wineprefix in wineprefixes:
                self.list_prefixes.add(BottlesImporterEntry(self.window, wineprefix))
        else:
            self.list_prefixes.add(BottlesImporterEntry(self.window, {}, sample=True))

    def import_backup_full(self, widget):
        file_dialog = Gtk.FileChooserDialog("Choose a backup archive",
                                            self.window,
                                            Gtk.FileChooserAction.OPEN,
                                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                            Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        filter_tar = Gtk.FileFilter()
        filter_tar.set_name(".tar.gz")
        filter_tar.add_pattern("*.tar.gz")
        file_dialog.add_filter(filter_tar)

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            self.runner.import_backup_bottle("full", file_dialog.get_filename())

        file_dialog.destroy()
