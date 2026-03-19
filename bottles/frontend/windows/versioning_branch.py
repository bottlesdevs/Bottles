# versioning_branch.py
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

from gettext import gettext as _
from gi.repository import Adw, Gtk

@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-versioning-branch.ui")
class VersioningBranchDialog(Adw.PreferencesDialog):
    __gtype_name__ = "VersioningBranchDialog"

    entry_name = Gtk.Template.Child()

    def __init__(self, parent, callback, **kwargs):
        super().__init__(**kwargs)
        self.parent = parent
        self.callback = callback
        
        self.entry_name.connect("apply", self.on_apply)

    def on_apply(self, widget):
        name = self.entry_name.get_text()
        if name and " " not in name:
            self.callback(name)
            self.close()
