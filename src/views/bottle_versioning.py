# bottle_versioning.py
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

import re
from gettext import gettext as _
from gi.repository import Gtk, GLib, Adw

from bottles.backend.models.result import Result

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.utils.common import open_doc_url
from bottles.widgets.state import StateEntry


@Gtk.Template(resource_path='/com/usebottles/bottles/details-versioning.ui')
class VersioningView(Adw.PreferencesPage):
    __gtype_name__ = 'DetailsVersioning'
    __registry = []

    # region Widgets
    list_states = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    pop_state = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    btn_help = Gtk.Template.Child()
    entry_state_comment = Gtk.Template.Child()
    status_page = Gtk.Template.Child()
    ev_controller = Gtk.EventControllerKey.new()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.versioning_manager = window.manager.versioning_manager
        self.config = config

        self.ev_controller.connect("key-released", self.check_entry_state_comment)
        self.entry_state_comment.add_controller(self.ev_controller)

        self.btn_save.connect("clicked", self.add_state)
        self.btn_help.connect("clicked", open_doc_url, "bottles/versioning")
        self.entry_state_comment.connect("activate", self.add_state)

    def add_state(self, widget):
        self.__registry.append(widget)
        self.list_states.append(widget)

    def empty_list(self):
        for r in self.__registry:
            if r.get_parent() is not None:
                r.get_parent().remove(r)
        self.__registry = []

    def update(self, widget=False, config=None, states=None):
        """
        This function update the states list with the
        ones from the bottle configuration.
        """
        if config is None:
            config = {}
        if states is None:
            states = {}
        if len(config) > 0:
            self.config = config

        self.list_states.set_sensitive(False)

        def new_state(_state):
            nonlocal self

            entry = StateEntry(
                window=self.window,
                config=self.config,
                state=_state
            )
            self.add_state(entry)

        def callback(result, error=False):
            nonlocal self
            
            self.status_page.set_visible(not result.status)
            self.list_states.set_visible(result.status)
            self.list_states.set_sensitive(result.status)

        def process_states():
            nonlocal self, states

            GLib.idle_add(self.empty_list)

            if len(states) == 0:
                states = self.versioning_manager.list_states(self.config)

            if len(states) == 0:
                return Result(False)

            if self.config.get("Versioning"):
                for state in states.items():
                    GLib.idle_add(new_state, state)

            return Result(True)

        RunAsync(process_states, callback)

    def check_entry_state_comment(self, widget, event_key):
        """
        This function check if the entry state comment is valid,
        looking for special characters. It also toggles the widget icon
        and the save button sensitivity according to the result.
        """
        regex = re.compile('[@!#$%^&*()<>?/|}{~:.;,"]')
        comment = self.entry_state_comment.get_text()
        check = regex.search(comment) is None

        self.btn_save.set_sensitive(check)
        self.entry_state_comment.set_icon_from_icon_name(
            1, '' if check else 'dialog-warning-symbolic"'
        )

    def add_state(self, widget):
        """
        This function create ask the versioning manager to
        create a new bottle state with the given comment.
        """
        if not self.btn_save.get_sensitive():
            return

        def update(result, error):
            if result.status:
                self.update(states=result.data.get('states'))

        comment = self.entry_state_comment.get_text()
        if comment != "":
            RunAsync(
                task_func=self.versioning_manager.create_state,
                callback=update,
                config=self.config,
                comment=comment
            )
            self.entry_state_comment.set_text("")
            self.pop_state.popdown()
