# drive.py
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

from gi.repository import Gtk, GLib, Handy

from bottles.backend.wine.drives import Drives  # pyright: reportMissingImports=false


@Gtk.Template(resource_path='/com/usebottles/bottles/drive-entry.ui')
class DriveEntry(Handy.ActionRow):
    __gtype_name__ = 'DriveEntry'

    # region Widgets
    btn_remove = Gtk.Template.Child()
    btn_path = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, drive, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.drive = drive

        '''
        Set the env var name as ActionRow title and set the
        entry_value to its value
        '''
        self.set_title(self.drive[0])
        self.set_subtitle(self.drive[1])

        # connect signals
        self.btn_path.connect("clicked", self.__choose_path)
        self.btn_remove.connect("clicked", self.__remove)

    def __choose_path(self, widget):
        """
        Open the file chooser dialog and set the path to the
        selected file
        """
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose path"),
            self.window,
            Gtk.FileChooserAction.SELECT_FOLDER,
            _("Select"),
            _("Cancel")
        )
        response = file_dialog.run()
        if response == -3:
            path = file_dialog.get_filename()
            Drives(self.config).new_drive(self.drive[0], path)
            self.set_subtitle(path)

    def __remove(self, widget):
        """
        Remove the drive from the bottle configuration and
        destroy the widget
        """
        Drives(self.config).remove_drive(self.drive[0])
        self.destroy()


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-drives.ui')
class DrivesDialog(Handy.Window):
    __gtype_name__ = 'DrivesDialog'

    # region Widgets
    combo_letter = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    list_drives = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.__populate_combo_letter()
        self.__populate_drives_list()

        # connect signals
        self.btn_save.connect("clicked", self.__save)

    def __idle_save(self, widget=False):
        """
        This function save the driveto the bottle configuration
        """
        drive_letter = self.combo_letter.get_active_id()

        self.list_drives.add(
            DriveEntry(
                window=self.window,
                config=self.config,
                drive=[drive_letter, ""]
            )
        )
        index = self.combo_letter.get_active()
        self.combo_letter.remove(index)
        self.combo_letter.set_active(0)

    def __save(self, widget=False):
        GLib.idle_add(self.__idle_save)

    def __idle_populate_vars_list(self):
        """
        This function populate the list of env vars
        with the existing ones from the bottle configuration
        """
        drives = Drives(self.config).get_all()
        for drive in drives:
            self.list_drives.add(
                DriveEntry(
                    window=self.window,
                    config=self.config,
                    drive=[drive, drives[drive]]
                )
            )

    def __populate_drives_list(self):
        GLib.idle_add(self.__idle_populate_vars_list)

    def __populate_combo_letter(self):
        drives = Drives(self.config).get_all()
        self.combo_letter.remove_all()

        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if letter not in drives:
                self.combo_letter.append(letter, letter)
                self.btn_save.set_sensitive(True)

        self.combo_letter.set_active(0)
