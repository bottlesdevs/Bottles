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

import string

from gi.repository import Gtk, GLib, Adw

from bottles.backend.wine.drives import Drives


@Gtk.Template(resource_path="/com/usebottles/bottles/drive-entry.ui")
class DriveEntry(Adw.ActionRow):
    __gtype_name__ = "DriveEntry"

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

        # Set env var name as ActionRow's title
        # and entry_value as its value
        self.set_title(self.drive[0])
        self.set_subtitle(self.drive[1])

        if "c" in self.drive[0].lower():
            self.btn_remove.set_visible(False)
            self.btn_path.set_visible(False)

        # connect signals
        self.btn_path.connect("clicked", self.__choose_path)
        self.btn_remove.connect("clicked", self.__remove)

    def __choose_path(self, *_args):
        """Open file chooser dialog and set path pointing to the selected one"""

        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = dialog.get_file().get_path()
            Drives(self.config).set_drive_path(self.drive[0], path)
            self.set_subtitle(path)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Drive Path"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            parent=self.parent.window,
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def __remove(self, *_args):
        """Remove drive from bottle's configuration and destroy its widget"""
        Drives(self.config).remove_drive(self.drive[0])
        self.parent.list_drives.remove(self)
        self.parent.add_combo_letter(self.drive[0])


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-drives.ui")
class DrivesDialog(Adw.Window):
    __gtype_name__ = "DrivesDialog"
    __alphabet = string.ascii_uppercase

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

        self.__populate_combo_and_drives()
        
        # connect signals
        self.btn_save.connect("clicked", self.__save)

    def __save(self, *_args):
        """Add a new drive to bottle's configuration"""
        index = self.combo_letter.get_selected()
        drive_letter = self.str_list_letters.get_string(index)
        _entry = DriveEntry(parent=self, drive=[drive_letter, ""])

        GLib.idle_add(self.list_drives.add, _entry)
        self.str_list_letters.remove(index)

    def __populate_combo_and_drives(self):
        """
        Populate lists of combo letters and drives
        based on the existing ones from bottle's configuration
        """
        drives = Drives(self.config).get_all()
        for letter in self.__alphabet:
            if letter not in drives:
                # Add to combo letters
                self.str_list_letters.append(letter)
                self.btn_save.set_sensitive(True)
            else:
                # Add to drives list
                _entry = DriveEntry(parent=self, drive=[letter, drives[letter]])
                GLib.idle_add(self.list_drives.add, _entry)

    def add_combo_letter(self, letter: str):
        idx_new = next(
            (i for i, c in enumerate(self.str_list_letters) if c.get_string() > letter),
            self.str_list_letters.get_n_items(),
        )
        self.str_list_letters.splice(idx_new, 0, letter)

