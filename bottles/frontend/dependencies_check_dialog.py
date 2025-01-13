# dependencies_check_dialog.py
#
# Copyright 2025 The Bottles Contributors
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

from gi.repository import Gtk, Adw


@Gtk.Template(resource_path="/com/usebottles/bottles/dependencies-check-dialog.ui")
class DependenciesCheckDialog(Adw.Window):
    __gtype_name__ = "DependenciesCheckDialog"

    # region widgets
    btn_quit = Gtk.Template.Child()

    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)
        self.window = window

        self.btn_quit.connect("clicked", self.__quit)

    def __quit(self, *_args):
        self.window.proper_close()
