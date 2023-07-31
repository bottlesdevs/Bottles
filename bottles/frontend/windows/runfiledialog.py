# runfiledialog.py
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

from gettext import gettext as _

from gi.repository import Gtk, Adw, Gio
from bottles.backend.managers.exepath import ExePathManager

from bottles.frontend.utils.filters import add_all_filters, add_executable_filters
from bottles.frontend.params import APP_ID

class RunFileDialog(Adw.ApplicationWindow):
    """This class should not be called from the application GUI, only from CLI."""
    __gtype_name__ = 'RunFileDialog'
    settings = Gio.Settings.new(APP_ID)
    Adw.init()

    def __init__(self, bottle: str, exe: str, **kwargs):
        super().__init__(**kwargs)
        def execute(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                self._exit()
                return
            
            exe_path_manager = ExePathManager()
            # map the flatpak mangled path to `exe`
            exe_path_manager.add_path(exe, dialog.get_file().get_path())
            import subprocess
            subprocess.Popen(['bottles-cli', 'run', '-b', bottle, '-e', dialog.get_file().get_path()])
            self._exit()

        fd = Gio.File.new_for_path(exe)

        dialog = Gtk.FileChooserNative.new(
            _("Select Executable"),
            self,
            Gtk.FileChooserAction.OPEN,
            _("Run"),
            None
        )
        import os.path
        if os.path.exists(fd.get_path()):
            dialog.set_file(fd)
        add_executable_filters(dialog)
        add_all_filters(dialog)
        dialog.connect("response", execute)
        dialog.show()

    def _exit(self):
        self.close()