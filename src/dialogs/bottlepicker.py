# bottlepicker.py
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
# pylint: disable=import-error,missing-docstring

import subprocess
from gi.repository import Gio, Gtk, Adw

from bottles.params import *  # pyright: reportMissingImports=false
from bottles.utils.connection import ConnectionUtils
from bottles.backend.managers.manager import Manager


class BottleEntry(Adw.ActionRow):
    def __init__(self, config):
        super().__init__()
        self.bottle = config[1]['Path']
        self.set_title(config[1]['Name'])


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-bottle-picker.ui')
class BottlePickerDialog(Adw.ApplicationWindow):
    """This class should not be called from the application GUI, only from CLI."""
    __gtype_name__ = 'BottlePickerDialog'
    default_settings = Gtk.Settings.get_default()
    utils_conn = ConnectionUtils(force_offline=True)
    settings = Gio.Settings.new(APP_ID)
    Adw.init()

    # region Widgets
    btn_cancel = Gtk.Template.Child()
    btn_select = Gtk.Template.Child()
    list_bottles = Gtk.Template.Child()
    btn_open = Gtk.Template.Child()
    # endregion

    def __init__(self, arg_exe, **kwargs):
        super().__init__(**kwargs)
        self.arg_exe = arg_exe
        mng = Manager(self, is_cli=True)
        mng.check_bottles()
        bottles = mng.local_bottles

        for b in bottles.items():
            self.list_bottles.append(BottleEntry(b))

        self.list_bottles.select_row(self.list_bottles.get_first_child())
        self.btn_cancel.connect('clicked', self.__close)
        self.btn_select.connect('clicked', self.__select)
        self.btn_open.connect('clicked', self.__open)

    @staticmethod
    def __close(*_args):
        quit()

    def __select(self, *_args):
        row = self.list_bottles.get_selected_row()
        if row:
            self.destroy()
            subprocess.Popen(["bottles-cli", "run", "-b", row.bottle, "-e", self.arg_exe])

    def __open(self, *_args):
        self.destroy()
        subprocess.Popen(["bottles"])
