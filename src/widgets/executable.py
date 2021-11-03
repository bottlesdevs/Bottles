# executable.py
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

from gi.repository import Gtk
from ..backend.runner import Runner


class ExecButton(Gtk.ModelButton):

    def __init__(self, data, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.data = data

        self.set_label(data.get('name'))
        self.connect('clicked', self.on_clicked)

        self.show_all()

    def on_clicked(self, widget):
        Runner.run_executable(
            config=self.config,
            file_path=self.data.get("file"),
            arguments=self.data.get("args"),
        )
