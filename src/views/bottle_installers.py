# bottle_installers.py
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
from gi.repository import Gtk

from bottles.utils.common import open_doc_url  # pyright: reportMissingImports=false
from bottles.widgets.installer import InstallerEntry


@Gtk.Template(resource_path='/com/usebottles/bottles/details-installers.ui')
class InstallersView(Gtk.ScrolledWindow):
    __gtype_name__ = 'DetailsInstallers'

    # region Widgets
    list_installers = Gtk.Template.Child()
    btn_help = Gtk.Template.Child()
    btn_toggle_search = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.btn_help.connect("clicked", open_doc_url, "bottles/installers")
        self.entry_search.connect('key-release-event', self.__search_installers)
        self.btn_toggle_search.connect('clicked', self.__toggle_search)
        self.entry_search.connect('changed', self.__search_installers)

    def __search_installers(self, widget, event=None, data=None):
        """
        This function search in the list of installers the
        text written in the search entry.
        """
        terms = widget.get_text()
        self.list_installers.set_filter_func(
            self.__filter_installers,
            terms
        )

    @staticmethod
    def __filter_installers(row, terms=None):
        text = row.get_title().lower() + row.get_subtitle().lower()
        if terms.lower() in text:
            return True
        return False

    def update(self, widget=False, config=None):
        """
        This function update the installers list with the
        supported by the manager.
        """
        if config is None:
            config = {}
        self.config = config

        for w in self.list_installers:
            w.destroy()

        supported_installers = self.manager.supported_installers.items()

        if len(supported_installers) > 0:
            for installer in supported_installers:
                if len(installer) != 2:
                    continue
                if installer[1].get("Arch", "win64") != self.config["Arch"]:
                    continue
                self.list_installers.add(
                    InstallerEntry(
                        window=self.window,
                        config=self.config,
                        installer=installer
                    )
                )

    def __toggle_search(self, widget):
        """
        This function toggle the search mode.
        """
        status = not self.search_bar.get_search_mode()
        self.search_bar.set_search_mode(status)
        if not status:
            self.entry_search.set_text("")
