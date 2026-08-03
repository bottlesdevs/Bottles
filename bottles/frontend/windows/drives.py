# drive.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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

import os
import string
from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk

from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.drives import Drives
from bottles.backend.wine.eject import Eject


@Gtk.Template(resource_path="/com/usebottles/bottles/drive-entry.ui")
class DriveEntry(Adw.EntryRow):
    __gtype_name__ = "DriveEntry"

    # region Widgets
    btn_remove = Gtk.Template.Child()
    btn_path = Gtk.Template.Child()
    btn_eject = Gtk.Template.Child()

    # endregion

    def __init__(self, parent, drive, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.manager = parent.window.manager
        self.config = parent.config
        self.drive = drive

        # Set the drive letter and current host path.
        self.set_title(self.drive[0])
        self.set_text(self.drive[1])

        if "c" in self.drive[0].lower():
            self.btn_remove.set_visible(False)
            self.btn_path.set_visible(False)
            self.btn_eject.set_visible(False)
        else:
            self.btn_eject.set_visible(
                Drives(self.config).is_ejectable(self.drive[0])
            )

        # connect signals
        self.connect("changed", self.__validate)
        self.connect("apply", self.__save)
        self.btn_path.connect("clicked", self.__choose_path)
        self.btn_remove.connect("clicked", self.__remove)
        self.btn_eject.connect("clicked", self.__eject)

        self.__validate()

    def __eject(self, *_args):
        drive = f"{self.drive[0].rstrip(':')}:"
        self.btn_eject.set_sensitive(False)

        def complete(result, error):
            self.btn_eject.set_sensitive(True)
            if error is not None or result is None or not result.status:
                self.parent.window.show_toast(
                    _("Could not eject drive {0}").format(drive)
                )
                return
            self.parent.window.show_toast(_("Drive {0} ejected").format(drive))

        RunAsync(Eject(self.config).cdrom, callback=complete, drive=drive)

    def __validate(self, *_args):
        path = self.get_text()
        valid = bool(path and os.path.isabs(path))
        self.set_show_apply_button(valid and path != self.drive[1])
        if path and not valid:
            self.add_css_class("error")
        else:
            self.remove_css_class("error")

    def __save(self, *_args):
        path = self.get_text()
        if not path or not os.path.isabs(path):
            return

        Drives(self.config).set_drive_path(self.drive[0], path)
        self.drive[1] = path
        self.__validate()

    def __choose_path(self, *_args):
        """Open file chooser dialog and set path pointing to the selected one"""

        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            selected_path = dialog.get_file().get_path()
            if not selected_path:
                return
            resolved_path = ManagerUtils.resolve_portal_path(selected_path)
            path = (
                resolved_path
                if resolved_path and os.path.isabs(resolved_path)
                else selected_path
            )
            self.set_text(path)
            self.__save()

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
            if letter == "C" and letter not in drives:
                continue
            if letter not in drives:
                # Add to combo letters
                self.str_list_letters.append(letter)
                self.btn_save.set_sensitive(True)
            else:
                # Add to drives list
                if letter == "C":
                    _entry = Adw.ActionRow(
                        title=letter,
                        subtitle=drives[letter],
                    )
                else:
                    _entry = DriveEntry(parent=self, drive=[letter, drives[letter]])
                GLib.idle_add(self.list_drives.add, _entry)

    def add_combo_letter(self, letter: str):
        idx_new = next(
            (i for i, c in enumerate(self.str_list_letters) if c.get_string() > letter),
            self.str_list_letters.get_n_items(),
        )
        self.str_list_letters.splice(idx_new, 0, letter)
