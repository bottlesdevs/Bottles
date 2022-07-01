# loading.py
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

from gi.repository import Gtk, Adw


@Gtk.Template(resource_path='/com/usebottles/bottles/loading.ui')
class LoadingView(Adw.Bin):
    __gtype_name__ = 'LoadingView'
    __fetched = 0

    # region widgets
    label_fetched = Gtk.Template.Child()
    label_downloading = Gtk.Template.Child()
    # endregion

    def add_fetched(self, total):
        self.__fetched += 1
        self.label_downloading.set_text(_("Downloading ~{0} of packages…").format("20kb"))
        self.label_fetched.set_text(_("Fetched {0} of {1} packages").format(self.__fetched, total))
