# executable.py
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

from gi.repository import Gtk

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.backend.runner import Runner
from bottles.backend.wine.executor import WineExecutor


class ExecButton(Gtk.Button):

    def __init__(self, parent, data, config, **kwargs):
        super().__init__(**kwargs)
        self.parent = parent
        self.config = config
        self.data = data

        self.set_label(data.get('name'))
        self.connect('clicked', self.on_clicked)

    def on_clicked(self, widget):
        executor = WineExecutor(
            self.config,
            exec_path=self.data.get("file"),
            args=self.data.get("args")
        )
        RunAsync(executor.run)
        self.parent.pop_run.popdown()  # workaround #1640
