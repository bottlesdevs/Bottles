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
from gi.repository import Gtk

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.utils.common import open_doc_url
from bottles.widgets.state import StateEntry


@Gtk.Template(resource_path='/com/usebottles/bottles/details-versioning.ui')
class VersioningView(Gtk.ScrolledWindow):
    __gtype_name__ = 'DetailsVersioning'

    # region Widgets
    list_states = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    pop_state = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    btn_help = Gtk.Template.Child()
    entry_state_comment = Gtk.Template.Child()
    hdy_status = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.versioning_manager = window.manager.versioning_manager
        self.config = config

        self.btn_save.connect("clicked", self.add_state)
        self.entry_state_comment.connect(
            'key-release-event', self.check_entry_state_comment
        )
        self.btn_help.connect(
            "clicked", open_doc_url, "bottles/versioning"
        )
        self.entry_state_comment.connect("activate", self.add_state)

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

        for w in self.list_states.get_children():
            w.destroy()

        if len(states) == 0:
            states = self.versioning_manager.list_states(self.config)

        states = states.items()
        self.hdy_status.set_visible(not len(states) > 0)

        if self.config.get("Versioning"):
            for state in states:
                self.list_states.add(
                    StateEntry(
                        window=self.window,
                        config=self.config,
                        state=state
                    )
                )

    def check_entry_state_comment(self, widget, event_key):
        """
        This function check if the entry state comment is valid,
        looking for special characters. It also toggle the widget icon
        and the save button sensitivity according to the result.
        """
        regex = re.compile('[@!#$%^&*()<>?/|}{~:.;,"]')
        comment = widget.get_text()
        check = regex.search(comment) is None

        self.btn_save.set_sensitive(check)
        widget.set_icon_from_icon_name(
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
