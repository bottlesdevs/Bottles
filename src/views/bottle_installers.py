# bottle_installers.py
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

from gettext import gettext as _
from gi.repository import Gtk

from ..utils import GtkUtils
from ..widgets.installer import InstallerEntry


@Gtk.Template(resource_path='/com/usebottles/bottles/details-installers.ui')
class InstallersView(Gtk.ScrolledWindow):
    __gtype_name__ = 'DetailsInstallers'

    # region Widgets
    list_installers = Gtk.Template.Child()
    btn_help = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.btn_help.connect(
            'pressed', GtkUtils.open_doc_url, "bottles/installers"
        )

    def update(self, widget=False, config={}):
        '''
        This function update the installers list with the
        supported by the manager.
        '''
        self.config = config
        
        for w in self.list_installers:
            w.destroy()

        supported_installers = self.manager.supported_installers.items()

        if len(supported_installers) > 0:
            for installer in supported_installers:
                self.list_installers.add(
                    InstallerEntry(
                        window=self.window,
                        config=self.config,
                        installer=installer
                    )
                )
