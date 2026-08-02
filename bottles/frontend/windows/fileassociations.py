# fileassociations.py
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

from gettext import gettext as _

from gi.repository import Adw, Gtk

from bottles.backend.utils.manager import ManagerUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-file-associations.ui")
class FileAssociationsDialog(Adw.Dialog):
    __gtype_name__ = "FileAssociationsDialog"

    entry_extensions = Gtk.Template.Child()
    banner_error = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()

    def __init__(self, window, extensions, on_save, **kwargs):
        super().__init__(**kwargs)

        self.window = window
        self.on_save = on_save
        self.entry_extensions.set_text(", ".join(extensions))

        self.btn_cancel.connect("clicked", lambda *_args: self.close())
        self.btn_save.connect("clicked", self.__save)
        self.entry_extensions.connect("changed", self.__validate)
        self.entry_extensions.connect("activate", self.__save)
        self.__validate()

    def present(self):
        return super().present(self.window)

    def __validate(self, *_args):
        text = self.entry_extensions.get_text()
        extensions, _mime_types, invalid = ManagerUtils.resolve_file_associations(text)
        valid = not invalid and (not text.strip() or bool(extensions))

        self.btn_save.set_sensitive(valid)
        self.entry_extensions.remove_css_class("error")
        self.banner_error.set_revealed(False)
        if invalid:
            self.entry_extensions.add_css_class("error")
            self.banner_error.set_title(
                _("These extensions are invalid or unknown to the system: {0}").format(
                    ", ".join(invalid)
                )
            )
            self.banner_error.set_revealed(True)

        return extensions, valid

    def __save(self, *_args):
        extensions, valid = self.__validate()
        if not valid:
            return

        self.on_save(extensions)
        self.close()
