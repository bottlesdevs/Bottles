# drive.py
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

from gi.repository import Gtk, GLib, Adw

from bottles.backend.wine.drives import Drives


@Gtk.Template(resource_path='/com/usebottles/bottles/drive-entry.ui')
class DriveEntry(Adw.ActionRow):
    __gtype_name__ = 'DriveEntry'

    # region Widgets
    btn_remove = Gtk.Template.Child()
    btn_path = Gtk.Template.Child()

    # endregion

    def __init__(self, parent, drive, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.manager = parent.window.manager
        self.config = parent.config
        self.drive = drive

        '''
        Set the env var name as ActionRow title and set the
        entry_value to its value
        '''
        self.set_title(self.drive[0])
        self.set_subtitle(self.drive[1])

        if "c" in self.drive[0].lower():
            self.btn_remove.set_visible(False)
            self.btn_path.set_visible(False)

        # connect signals
        self.btn_path.connect("clicked", self.__choose_path)
        self.btn_remove.connect("clicked", self.__remove)

    def __choose_path(self, *_args):
        """
        Open the file chooser dialog and set the path to the
        selected file
        """
        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = dialog.get_file().get_path()
            Drives(self.config).set_drive_path(self.drive[0], path)
            self.set_subtitle(path)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Drive Path"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            parent=self.parent.window
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def __remove(self, *_args):
        """
        Remove the drive from the bottle configuration and
        destroy the widget
        """
        Drives(self.config).remove_drive(self.drive[0])
        self.parent.list_drives.remove(self)
        self.parent.add_combo_letter(self.drive[0])


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-drives.ui')
class DrivesDialog(Adw.Window):
    __gtype_name__ = 'DrivesDialog'
    __alphabet = ["A", "B", "D", "E", "F", "G", "H",
                  "I", "J", "K", "L", "M", "N", "O",
                  "P", "Q", "R", "S", "T", "U", "V",
                  "W", "X", "Y", "Z"]

    # region Widgets
    combo_letter = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    list_drives = Gtk.Template.Child()
    str_list_letters = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.__populate_drives_list()
        self.__populate_combo_letter()

        # connect signals
        self.btn_save.connect("clicked", self.__save)

    def __save(self, *_args):
        """
        This function add a new drive to the bottle configuration
        """
        index = self.combo_letter.get_selected()
        drive_letter = self.str_list_letters.get_string(index)
        _entry = DriveEntry(parent=self, drive=[drive_letter, ""])

        GLib.idle_add(self.list_drives.add, _entry)
        self.str_list_letters.remove(index)

    def __populate_drives_list(self):
        """
        This function populate the list of drives
        with the existing ones from the bottle configuration
        """
        drives = Drives(self.config).get_all()
        for drive in drives:
            _entry = DriveEntry(parent=self, drive=[drive, drives[drive]])
            GLib.idle_add(self.list_drives.add, _entry)
            if drive in self.__alphabet:
                self.__alphabet.pop(self.__alphabet.index(drive))

    def __populate_combo_letter(self):
        drives = Drives(self.config).get_all()
        self.str_list_letters.splice(0, self.str_list_letters.get_n_items())

        for letter in self.__alphabet:
            if letter not in drives:
                self.str_list_letters.append(letter)
                self.btn_save.set_sensitive(True)

        self.combo_letter.set_selected(0)

    def add_combo_letter(self, letter):
        list_copy = list(map(lambda item: item.get_string(), self.str_list_letters))

        self.str_list_letters.splice(0, self.str_list_letters.get_n_items())

        for item in self.__alphabet:
            if item in list_copy or item == letter:
                self.str_list_letters.append(item)

        self.combo_letter.set_selected(0)
    