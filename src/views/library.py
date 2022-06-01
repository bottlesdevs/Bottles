# library.py
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

import logging
from datetime import datetime
from gettext import gettext as _
from gi.repository import Gtk, Gdk, GLib, Adw

from bottles.backend.managers.library import LibraryManager  # pyright: reportMissingImports=false
from bottles.widgets.library import LibraryEntry


@Gtk.Template(resource_path='/com/usebottles/bottles/library.ui')
class LibraryView(Adw.Bin):
    __gtype_name__ = 'LibraryView'

    # region Widgets
    main_flow = Gtk.Template.Child()
    adw_status = Gtk.Template.Child()
    btn_update = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.window = window

        self.btn_back.connect("clicked", self.go_back)
        #window.set_actions(self.actions)
        self.update()

    def update(self):
        library_manager = LibraryManager()
        entries = library_manager.get_library()

        while self.main_flow.get_first_child() is not None:
            self.main_flow.remove(self.main_flow.get_first_child())

        self.adw_status.set_visible(len(entries) == 0)
        self.main_flow.set_visible(len(entries) == 0)

        for u, e in entries.items():
            entry = LibraryEntry(self, u, e)
            self.main_flow.append(entry)

    def remove_entry(self, uuid):
        library_manager = LibraryManager()
        library_manager.remove_from_library(uuid)
        self.update()

    def go_back(self, widget=False):
        self.window.main_leaf.navigate(Adw.NavigationDirection.BACK)