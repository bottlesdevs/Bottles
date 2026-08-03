# programbackups.py
#
# Copyright 2026 mirkobrombin <brombin94@gmail.com>
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

import os
from gettext import gettext as _

from gi.repository import Adw, Gio, GLib, Gtk

from bottles.backend.logger import Logger
from bottles.backend.managers.backup import BackupManager
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-program-backups.ui")
class ProgramBackupsDialog(Adw.Dialog):
    __gtype_name__ = "ProgramBackupsDialog"

    switch_enabled = Gtk.Template.Child()
    action_destination = Gtk.Template.Child()
    btn_destination = Gtk.Template.Child()
    btn_destination_reset = Gtk.Template.Child()
    btn_open_destination = Gtk.Template.Child()
    list_paths = Gtk.Template.Child()
    label_paths_empty = Gtk.Template.Child()
    btn_add_files = Gtk.Template.Child()
    btn_add_folder = Gtk.Template.Child()
    spin_keep = Gtk.Template.Child()
    banner_error = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()

    def __init__(self, parent, config, program, on_save, **kwargs):
        super().__init__(**kwargs)

        self.parent = parent
        self.window = getattr(parent, "window", parent)
        self.config = config
        self.program = program
        self.on_save = on_save

        settings = program.get("automatic_backup")
        if not isinstance(settings, dict):
            settings = {}
        self.destination = settings.get("destination", "")
        if not isinstance(self.destination, str):
            self.destination = ""
        self.paths = [
            path for path in settings.get("paths", []) if isinstance(path, str) and path
        ]

        self.switch_enabled.set_active(bool(settings.get("enabled")))
        self.spin_keep.set_value(self._valid_keep(settings.get("keep", 5)))

        self.btn_cancel.connect("clicked", lambda *_args: self.close())
        self.btn_save.connect("clicked", self.__save)
        self.btn_destination.connect("clicked", self.__select_destination)
        self.btn_destination_reset.connect("clicked", self.__reset_destination)
        self.btn_open_destination.connect("clicked", self.__open_destination)
        self.btn_add_files.connect("clicked", self.__add_files)
        self.btn_add_folder.connect("clicked", self.__add_folder)
        self.switch_enabled.connect("notify::active", self.__update_validation)

        self.__populate_paths()
        self.__update_destination()
        self.__update_validation()

    def present(self):
        return super().present(self.parent)

    @staticmethod
    def _valid_keep(value) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 5
        return min(max(value, 1), 20)

    def __set_initial_folder(self, dialog, path):
        if path and os.path.isdir(path):
            dialog.set_initial_folder(Gio.File.new_for_path(path))

    def __display_path(self, path):
        return BackupManager.resolve_program_backup_path(self.config, path) or path

    def __populate_paths(self):
        child = self.list_paths.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.list_paths.remove(child)
            child = next_child

        for path in self.paths:
            display_path = self.__display_path(path)
            title = os.path.basename(display_path.rstrip(os.sep)) or display_path
            row = Adw.ActionRow(title=title, subtitle=display_path)
            button = Gtk.Button(
                icon_name="user-trash-symbolic",
                tooltip_text=_("Remove"),
                valign=Gtk.Align.CENTER,
            )
            button.add_css_class("flat")
            button.connect("clicked", self.__remove_path, path)
            row.add_suffix(button)
            self.list_paths.append(row)

        has_paths = bool(self.paths)
        self.list_paths.set_visible(has_paths)
        self.label_paths_empty.set_visible(not has_paths)

    def __add_path(self, path):
        if not path:
            return
        path = BackupManager.serialize_program_backup_path(self.config, path)
        if path is None:
            self.window.show_toast(
                _("Select files and folders within the bottle, not the bottle itself.")
            )
            return
        if path not in self.paths:
            self.paths.append(path)
            self.__populate_paths()
            self.__update_validation()

    def __remove_path(self, _button, path):
        self.paths.remove(path)
        self.__populate_paths()
        self.__update_validation()

    def __add_files(self, *_args):
        def selected(dialog, result):
            try:
                files = dialog.open_multiple_finish(result)
                for index in range(files.get_n_items()):
                    self.__add_path(files.get_item(index).get_path())
            except GLib.Error as error:
                if error.code != 2:
                    logging.warning(f"Error selecting backup files: {error}")

        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Select Files to Back Up"))
        self.__set_initial_folder(dialog, ManagerUtils.get_bottle_path(self.config))
        dialog.open_multiple(parent=self.parent, callback=selected)

    def __add_folder(self, *_args):
        def selected(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
                if folder:
                    self.__add_path(folder.get_path())
            except GLib.Error as error:
                if error.code != 2:
                    logging.warning(f"Error selecting backup folder: {error}")

        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Select Folder to Back Up"))
        self.__set_initial_folder(dialog, ManagerUtils.get_bottle_path(self.config))
        dialog.select_folder(parent=self.parent, callback=selected)

    def __select_destination(self, *_args):
        def selected(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
                if folder and folder.get_path():
                    self.destination = folder.get_path()
                    self.__update_destination()
                    self.__update_validation()
            except GLib.Error as error:
                if error.code != 2:
                    logging.warning(f"Error selecting backup destination: {error}")

        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Select Backup Folder"))
        self.__set_initial_folder(dialog, self.destination)
        dialog.select_folder(parent=self.parent, callback=selected)

    def __reset_destination(self, *_args):
        self.destination = ""
        self.__update_destination()
        self.__update_validation()

    def __update_destination(self):
        if self.destination:
            self.action_destination.set_subtitle(self.destination)
        else:
            self.action_destination.set_subtitle(
                _("Choose where automatic backups are stored.")
            )
        self.btn_destination_reset.set_visible(bool(self.destination))
        self.btn_open_destination.set_visible(bool(self.destination))

    def __open_destination(self, *_args):
        if not self.destination:
            return
        program = dict(self.program)
        program["automatic_backup"] = {"destination": self.destination}
        root = BackupManager.get_program_backup_root(self.config, program)
        path = root if os.path.isdir(root) else self.destination
        ManagerUtils.open_filemanager(path_type="custom", custom_path=path)

    def __update_validation(self, *_args):
        destination_available = os.path.isdir(self.destination)
        destination_valid = BackupManager.is_program_backup_destination_valid(
            self.config, self.destination
        )
        paths_available = any(
            resolved and os.path.lexists(resolved)
            for resolved in (
                BackupManager.resolve_program_backup_path(self.config, path)
                for path in self.paths
            )
        )
        valid = destination_available and destination_valid and paths_available
        enabled = self.switch_enabled.get_active()
        self.btn_save.set_sensitive(not enabled or valid)
        self.banner_error.set_revealed(enabled and not valid)
        if self.destination and not destination_available:
            self.banner_error.set_title(_("Choose an available backup folder."))
        elif self.destination and not destination_valid:
            self.banner_error.set_title(_("Choose a backup folder outside the bottle."))
        elif self.paths and not paths_available:
            self.banner_error.set_title(
                _("Choose at least one available file or folder.")
            )
        else:
            self.banner_error.set_title(
                _("Select a backup folder and at least one file or folder.")
            )

    def __save(self, *_args):
        if not self.btn_save.get_sensitive():
            return
        self.on_save(
            {
                "enabled": self.switch_enabled.get_active(),
                "destination": self.destination,
                "paths": self.paths,
                "keep": int(self.spin_keep.get_value()),
            }
        )
        self.close()
