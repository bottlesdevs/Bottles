# state.py
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

from datetime import datetime
from gi.repository import Gtk, GLib, Adw
from gettext import gettext as _

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.dialogs.generic import SourceDialog


@Gtk.Template(resource_path='/com/usebottles/bottles/state-entry.ui')
class StateEntry(Adw.ActionRow):
    __gtype_name__ = 'StateEntry'

    # region Widgets
    btn_restore = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    spinner = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, state, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.state = state
        self.state_name = "State: {0}".format(state[0])
        self.config = config
        self.versioning_manager = self.manager.versioning_manager

        # format creation date
        creation_date = datetime.strptime(
            state[1].get("Creation_Date"), "%Y-%m-%d %H:%M:%S.%f"
        )
        creation_date = creation_date.strftime("%d %B %Y, %H:%M")
        
        self.state_name = "#{0} - {1}".format(state[0], creation_date)
        # populate widgets
        self.set_title(self.state_name)
        self.set_subtitle(self.state[1].get("Comment"))
        if state[0] == config.get("State"):
            self.add_css_class("current-state")

        # connect signals
        self.btn_restore.connect("clicked", self.set_state)
        self.btn_manifest.connect("clicked", self.open_index)

    def set_state(self, widget):
        """
        Set the bottle state to this one.
        """
        widget.set_sensitive(False)
        self.spinner.show()
        GLib.idle_add(self.spinner.start)
        RunAsync(
            task_func=self.versioning_manager.set_state,
            config=self.config,
            state_id=self.state[0],
            after=self.set_completed
        )

    def open_index(self, widget):
        """
        Open the manifest for the state index in a new
        dialog.
        """
        plain_state = self.versioning_manager.get_state_edits(
            self.config,
            self.state[0],
            True
        ).get("Plain")

        SourceDialog(
            parent=self.window,
            title=_("Index for state {0}").format(self.state[0]),
            message=plain_state
        ).present()

    def set_completed(self):
        """
        Set completed status to the widget.
        """
        self.spinner.stop()
        self.btn_restore.set_visible(False)
        self.set_sensitive(True)
