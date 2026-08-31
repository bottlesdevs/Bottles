# library.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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

from gi.repository import Adw, GObject, Gtk

from bottles.backend.managers.library import LibraryManager
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.utils.umu import get_umu_store_title
from bottles.frontend.widgets.library import LibraryAddEntry, LibraryEntry


def _ordered_library_entries(entries):
    return sorted(
        entries.items(),
        key=lambda item: str(item[1].get("name") or "").casefold(),
    )


@Gtk.Template(resource_path="/com/usebottles/bottles/library.ui")
class LibraryView(Adw.Bin):
    __gtype_name__ = "LibraryView"

    # region Widgets
    scroll_window = Gtk.Template.Child()
    stack_content = Gtk.Template.Child()
    main_flow = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    style_provider = Gtk.CssProvider()
    # endregion

    items_per_line = GObject.property(type=int, default=0)  # type: ignore

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.window = window
        self.css = b""
        self.entry_search.connect("search-changed", self.__search)
        self.main_flow.set_filter_func(self.__filter_entry)
        self.update()

    def update(self):
        library_manager = LibraryManager()
        entries = library_manager.get_library()

        while self.main_flow.get_first_child() is not None:
            self.main_flow.remove(self.main_flow.get_first_child())

        entry_count = 0

        for u, e in _ordered_library_entries(entries):
            # We suppress exceptions so that it doesn't continue if the init fails
            with contextlib.suppress(Exception):
                entry = LibraryEntry(self, u, e)
                self.main_flow.append(entry)
                entry_count += 1

        if entry_count == 0:
            self.main_flow.append(LibraryAddEntry(self))
        self.items_per_line = max(entry_count, 1)
        self.__search()

    def __search(self, *_args):
        self.main_flow.invalidate_filter()
        query = self.entry_search.get_text().strip()
        if not query:
            self.stack_content.set_visible_child_name("library")
            return

        child = self.main_flow.get_first_child()
        while child is not None:
            entry = child.get_child()
            if not isinstance(entry, LibraryAddEntry) and self.__filter_entry(child):
                self.stack_content.set_visible_child_name("library")
                return
            child = child.get_next_sibling()
        self.stack_content.set_visible_child_name("empty")

    def __filter_entry(self, child):
        entry = child.get_child()
        if isinstance(entry, LibraryAddEntry):
            return True
        query = self.entry_search.get_text().strip().casefold()
        if not query:
            return True
        values = (
            entry.name,
            entry.entry.get("source", ""),
            entry.entry.get("bottle", {}).get("name", ""),
        )
        if entry.is_umu:
            states = {
                "draft": _("Choose Executable"),
                "installing": _("Installing"),
                "failed": _("Installation Failed"),
                "stopped": _("Installation Stopped"),
                "ready": _("Ready"),
            }
            values += (
                get_umu_store_title(entry.game.store),
                states.get(entry.game.state, entry.game.state),
            )
        return query in " ".join(str(value or "") for value in values).casefold()

    def show_bottle_programs(self, *_args):
        self.window.show_list_view()
        self.window.show_toast(
            _("Open a Bottle and choose Add to Library from one of its programs.")
        )

    def remove_entry(self, entry):
        previous_items_per_line = self.items_per_line

        @GtkUtils.run_in_main_loop
        def undo_callback(*args):
            self.items_per_line = previous_items_per_line
            entry.show()

        @GtkUtils.run_in_main_loop
        def dismissed_callback(*args):
            self.__delete_entry(entry)

        entry.hide()
        self.items_per_line = max(self.items_per_line - 1, 1)
        self.window.show_toast(
            message=_('"{0}" removed from the library.').format(entry.name),
            timeout=5,
            action_label=_("Undo"),
            action_callback=undo_callback,
            dismissed_callback=dismissed_callback,
        )

    def __delete_entry(self, entry):
        library_manager = LibraryManager()
        library_manager.remove_from_library(entry.uuid, entry.config)
        self.update()

    def go_back(self, widget=False):
        self.window.main_leaf.navigate(Adw.NavigationDirection.BACK)
