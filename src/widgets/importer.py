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

from gi.repository import Gtk, Adw

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils


@Gtk.Template(resource_path='/com/usebottles/bottles/importer-entry.ui')
class ImporterEntry(Adw.ActionRow):
    __gtype_name__ = 'ImporterEntry'

    # region Widgets
    label_manager = Gtk.Template.Child()
    btn_import = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    img_lock = Gtk.Template.Child()

    # endregion

    def __init__(self, window, prefix, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.import_manager = window.manager.import_manager
        self.prefix = prefix

        # populate widgets
        self.set_title(prefix.get("Name"))
        self.label_manager.set_text(prefix.get("Manager"))

        if prefix.get("Lock"):
            self.img_lock.set_visible(True)

        self.label_manager.get_style_context().add_class(
            "tag-%s" % prefix.get("Manager").lower()
        )

        # connect signals
        self.btn_browse.connect("clicked", self.browse_wineprefix)
        self.btn_import.connect("clicked", self.import_wineprefix)

    '''Browse wineprefix files'''

    def browse_wineprefix(self, widget):
        ManagerUtils.browse_wineprefix(self.prefix)

    '''Import wineprefix'''

    def import_wineprefix(self, widget):
        def set_imported(result, error=False):
            if result.status:
                self.destroy()

            self.set_sensitive(True)

        self.set_sensitive(False)

        RunAsync(
            self.import_manager.import_wineprefix,
            callback=set_imported,
            wineprefix=self.prefix
        )
