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
from gi.repository import Gtk, Adw

from bottles.utils.common import open_doc_url  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils


@Gtk.Template(resource_path='/com/usebottles/bottles/details-programs.ui')
class ProgramsView(Adw.PreferencesPage):
    __gtype_name__ = 'DetailsPrograms'

    # region Widgets
    list_programs = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    btn_help = Gtk.Template.Child()
    btn_update = Gtk.Template.Child()
    btn_toggle_removed = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    hdy_status = Gtk.Template.Child()

    # endregion

    def __init__(self, parent, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.window = parent.window
        self.manager = parent.manager
        self.config = config
        self.show_removed = False

        self.btn_add.connect("clicked", self.add)
        self.btn_update.connect("clicked", self.parent.update_programs, self.config)
        self.btn_help.connect("clicked", open_doc_url, "bottles/programs")
        self.btn_toggle_removed.connect("clicked", self.__toggle_removed)

    def add(self, widget=False):
        """
        This function popup the add program dialog to the user. It
        will also update the bottle configuration, appending the
        path to the program picked by the user. It will also update
        the programs list.
        The file chooser path is set to the bottle path by default.
        """
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose an executable path"),
            self.window,
            Gtk.FileChooserAction.OPEN,
            _("Add"),
            _("Cancel")
        )
        file_dialog.set_current_folder(ManagerUtils.get_bottle_path(self.config))
        response = file_dialog.run()

        if response == -3:
            _file = file_dialog.get_filename()
            _file_name = _file.split("/")[-1]
            _program = {
                "executable": _file_name,
                "name": _file.split("/")[-1][:-4],
                "path": _file
            }
            self.manager.update_config(
                config=self.config,
                key=_file_name,
                value=_program,
                scope="External_Programs",
                fallback=True
            )
            self.parent.update_programs(config=self.config)

        file_dialog.destroy()

    def update(self, widget=False, config=None):
        """
        This function update the programs lists. The list in the
        details' page is limited to 5 items.
        """
        if config is None:
            config = {}

        self.config = config
        self.window.page_details.update_programs(config)

    def __toggle_removed(self, widget=False):
        """
        This function toggle the show_removed variable.
        """
        self.show_removed = not self.show_removed
        self.update(config=self.config)

    def empty_list(self):
        """
        This function empty the programs list.
        """
        while self.list_programs.get_first_child():
            self.list_programs.remove(self.list_programs.get_first_child())
