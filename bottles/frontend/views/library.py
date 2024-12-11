# library.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
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
from gettext import gettext as _

from gi.repository import Gtk, Adw, GObject

from bottles.backend.managers.library import LibraryManager
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.widgets.library import LibraryEntry


@Gtk.Template(resource_path="/com/usebottles/bottles/library.ui")
class LibraryView(Adw.Bin):
    __gtype_name__ = "LibraryView"

    # region Widgets
    scroll_window = Gtk.Template.Child()
    main_flow = Gtk.Template.Child()
    status_page = Gtk.Template.Child()
    style_provider = Gtk.CssProvider()
    # endregion

    items_per_line = GObject.property(type=int, default=0)  # type: ignore

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.window = window
        self.css = b""
        self.update()

    def update(self):
        library_manager = LibraryManager()
        entries = library_manager.get_library()

        while self.main_flow.get_first_child() is not None:
            self.main_flow.remove(self.main_flow.get_first_child())

        self.status_page.set_visible(len(entries) == 0)
        self.scroll_window.set_visible(not len(entries) == 0)

        self.items_per_line = len(entries)

        for u, e in entries.items():
            # We suppress exceptions so that it doesn't continue if the init fails
            with contextlib.suppress(Exception):
                entry = LibraryEntry(self, u, e)
                self.main_flow.append(entry)

    def remove_entry(self, entry):
        @GtkUtils.run_in_main_loop
        def undo_callback(*args):
            self.items_per_line += 1
            entry.show()

        @GtkUtils.run_in_main_loop
        def dismissed_callback(*args):
            self.__delete_entry(entry)

        entry.hide()
        self.items_per_line -= 1
        self.window.show_toast(
            message=_('"{0}" removed from the library.').format(entry.name),
            timeout=5,
            action_label=_("Undo"),
            action_callback=undo_callback,
            dismissed_callback=dismissed_callback,
        )

    def __delete_entry(self, entry):
        library_manager = LibraryManager()
        library_manager.remove_from_library(entry.uuid)

    def go_back(self, widget=False):
        self.window.main_leaf.navigate(Adw.NavigationDirection.BACK)
