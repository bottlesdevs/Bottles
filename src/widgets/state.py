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
from gi.repository import Gtk, GLib, Handy

from ..dialogs.generic import Dialog


@Gtk.Template(resource_path='/com/usebottles/bottles/state-entry.ui')
class StateEntry(Handy.ActionRow):
    __gtype_name__ = 'StateEntry'

    # region Widgets
    label_creation_date = Gtk.Template.Child()
    btn_restore = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
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
        self.spinner = Gtk.Spinner()

        '''Format creation date'''
        creation_date = datetime.strptime(state[1].get(
            "Creation_Date"), "%Y-%m-%d %H:%M:%S.%f")
        creation_date = creation_date.strftime("%b %d %Y %H:%M:%S")

        '''Populate widgets'''
        self.set_title(self.state_name)
        self.set_subtitle(self.state[1].get("Comment"))
        self.label_creation_date.set_text(creation_date)
        if state[0] == config.get("State"):
            self.get_style_context().add_class("current-state")

        # connect signals
        self.btn_restore.connect('pressed', self.set_state)
        self.btn_manifest.connect('pressed', self.open_index)

    '''Set bottle state'''

    def set_state(self, widget):
        for w in widget.get_children():
            w.destroy()
        self.get_parent().set_sensitive(False)

        widget.set_sensitive(False)
        widget.add(self.spinner)

        self.spinner.show()
        GLib.idle_add(self.spinner.start)
        self.versioning_manager.set_bottle_state(
            self.config, self.state[0], self.set_completed)

    '''Open state index'''

    def open_index(self, widget):
        dialog = Dialog(
            parent=self.window,
            title=_("Index for state {0}").format(self.state[0]),
            message=False,
            log=self.versioning_manager.get_bottle_state_edits(
                self.config,
                self.state[0],
                True))
        dialog.run()
        dialog.destroy()

    '''Set installed status'''

    def set_completed(self):
        self.spinner.stop()
        self.btn_restore.set_visible(False)
        self.get_parent().set_sensitive(True)
