# details_versioning_page.py
#
# Copyright 2025 The Bottles Contributors
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

import re
from gettext import gettext as _

from gi.repository import Gtk, GLib, Adw

from bottles.backend.models.result import Result
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.common import open_doc_url
from bottles.frontend.gtk import GtkUtils
from bottles.frontend.state_row import StateRow


@Gtk.Template(resource_path="/com/usebottles/bottles/details-versioning-page.ui")
class DetailsVersioningPage(Adw.Bin):
    __gtype_name__ = "DetailsVersioningPage"
    __registry = []

    # region Widgets
    list_states = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    pop_state = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    btn_help = Gtk.Template.Child()
    entry_state_message = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    ev_controller = Gtk.EventControllerKey.new()

    # endregion

    def __init__(self, details, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = details.window
        self.manager = details.window.manager
        self.versioning_manager = details.window.manager.versioning_manager
        self.config = config

        self.ev_controller.connect("key-released", self.check_entry_state_message)
        self.entry_state_message.add_controller(self.ev_controller)

        self.btn_save.connect("clicked", self.add_state)
        self.btn_help.connect("clicked", open_doc_url, "bottles/versioning")
        self.entry_state_message.connect("activate", self.add_state)

        self.stack = self.get_child()

    def empty_list(self):
        for r in self.__registry:
            if r.get_parent() is not None:
                r.get_parent().remove(r)
        self.__registry = []

    @GtkUtils.run_in_main_loop
    def update(self, widget=None, config=None, states=None, active=0):
        """
        This function update the states list with the
        ones from the bottle configuration.
        """
        if config is None:
            config = self.config
        if states is None:
            states = self.versioning_manager.list_states(config)
            if not config.Versioning:
                active = states.data.get("state_id")
                states = states.data.get("states")

        self.config = config
        self.list_states.set_sensitive(False)

        if self.config.Versioning:
            self.btn_add.set_sensitive(False)
            self.btn_add.set_tooltip_text(
                _("Please migrate to the new Versioning system to create new states.")
            )

        def new_state(_state, active):
            entry = StateRow(
                parent=self, config=self.config, state=_state, active=active
            )
            self.__registry.append(entry)
            self.list_states.append(entry)

        def callback(result, error=False):
            if result.status:
                self.stack.set_visible_child_name("states-list-page")
            else:
                self.stack.set_visible_child_name("empty-page")

        def process_states():
            GLib.idle_add(self.empty_list)

            if len(states) == 0:
                return Result(False)

            for state in states.items():
                _active = int(state[0]) == int(active)
                GLib.idle_add(new_state, state, _active)

            return Result(True)

        RunAsync(process_states, callback)

    def check_entry_state_message(self, *_args):
        """
        This function check if the entry state message is valid,
        looking for special characters. It also toggles the widget icon
        and the save button sensitivity according to the result.
        """
        regex = re.compile('[@!#$%^&*()<>?/|}{~:.;,"]')
        message = self.entry_state_message.get_text()
        check = regex.search(message) is None

        self.btn_save.set_sensitive(check)
        self.entry_state_message.set_icon_from_icon_name(
            1, "" if check else 'dialog-warning-symbolic"'
        )

    def add_state(self, widget):
        """
        This function create ask the versioning manager to
        create a new bottle state with the given message.
        """
        if not self.btn_save.get_sensitive():
            return

        @GtkUtils.run_in_main_loop
        def update(result, error):
            self.window.show_toast(result.message)
            if result.ok:
                self.update(
                    states=result.data.get("states"), active=result.data.get("state_id")
                )

        message = self.entry_state_message.get_text()
        if message != "":
            RunAsync(
                task_func=self.versioning_manager.create_state,
                callback=update,
                config=self.config,
                message=message,
            )
            self.entry_state_message.set_text("")
            self.pop_state.popdown()
