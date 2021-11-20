# bottle_programs.py
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

from ..widgets.program import ProgramEntry
from ..backend.manager_utils import ManagerUtils


@Gtk.Template(resource_path='/com/usebottles/bottles/details-programs.ui')
class ProgramsView(Gtk.ScrolledWindow):
    __gtype_name__ = 'DetailsPrograms'

    # region Widgets
    list_programs = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

    def add(self, widget=False):
        '''
        This function popup the add program dialog to the user. It
        will also update the bottle configuration, appending the
        path to the program picked by the user. It will also update
        the programs list.
        The file chooser path is set to the bottle path by default.
        '''
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose an executable path"),
            self.window,
            Gtk.FileChooserAction.OPEN,
            _("Add"),
            _("Cancel")
        )
        file_dialog.set_current_folder(
            ManagerUtils.get_bottle_path(self.config)
        )
        response = file_dialog.run()

        if response == -3:
            self.manager.update_config(
                config=self.config,
                key=file_dialog.get_filename().split("/")[-1][:-4],
                value=file_dialog.get_filename(),
                scope="External_Programs"
            )
            self.update_programs()

        file_dialog.destroy()

    def update(self, widget=False, config={}):
        '''
        This function update the programs lists. The list in the
        details page is limited to 5 items.
        '''
        self.config = config
        
        for w in self.list_programs:
            w.destroy()

        programs = self.manager.get_programs(self.config)

        i = 0
        for program in programs:
            self.list_programs.add(
                ProgramEntry(
                    self.window, self.config, program
                )
            )
