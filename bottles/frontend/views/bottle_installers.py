# bottle_installers.py
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

import time
from gi.repository import Gtk, GLib, Adw

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result

from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.common import open_doc_url
from bottles.frontend.widgets.installer import InstallerEntry


@Gtk.Template(resource_path='/com/usebottles/bottles/details-installers.ui')
class InstallersView(Adw.Bin):
    __gtype_name__ = 'DetailsInstallers'
    __registry = []

    # region Widgets
    list_installers = Gtk.Template.Child()
    btn_help = Gtk.Template.Child()
    btn_toggle_search = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    pref_page = Gtk.Template.Child()
    status_page = Gtk.Template.Child()
    ev_controller = Gtk.EventControllerKey.new()

    # endregion

    def __init__(self, details, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = details.window
        self.manager = details.window.manager
        self.config = config

        self.ev_controller.connect("key-released", self.__search_installers)
        self.entry_search.add_controller(self.ev_controller)

        self.search_bar.set_key_capture_widget(self.window)
        self.btn_help.connect("clicked", open_doc_url, "bottles/installers")
        self.entry_search.connect('changed', self.__search_installers)

    def __search_installers(self, *_args):
        """
        This function search in the list of installers the
        text written in the search entry.
        """
        terms = self.entry_search.get_text()
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

    def empty_list(self):
        for r in self.__registry:
            if r.get_parent() is not None:
                r.get_parent().remove(r)
        self.__registry = []

    def update(self, widget=False, config=None):
        """
        This function update the installers list with the
        supported by the manager.
        """
        if config is None:
            config = BottleConfig()
        self.config = config
        installers = self.manager.supported_installers.items()

        self.list_installers.set_sensitive(False)

        def new_installer(_installer):
            entry = InstallerEntry(
                window=self.window,
                config=self.config,
                installer=_installer
            )
            self.list_installers.append(entry)
            self.__registry.append(entry)

        def callback(result, error=False):
            self.status_page.set_visible(not result.status)
            self.pref_page.set_visible(result.status)
            self.list_installers.set_visible(result.status)
            self.list_installers.set_sensitive(result.status)

        def process_installers():
            time.sleep(.5)  # workaround for freezing bug on bottle load
            GLib.idle_add(self.empty_list)

            if len(installers) == 0:
                return Result(False)

            i = 0

            for installer in installers:
                if len(installer) != 2:
                    continue
                if installer[1].get("Arch", "win64") != self.config.Arch:
                    continue
                GLib.idle_add(new_installer, installer)
                i += 1

            if i == 0:
                return Result(False)  # there are no arch-compatible installers

            return Result(True)

        RunAsync(process_installers, callback)
