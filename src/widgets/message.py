# message.py
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

import webbrowser
from gi.repository import Gtk, Adw
from gettext import gettext as _

from bottles.backend.managers.notifications import NotificationsManager  # pyright: reportMissingImports=false


@Gtk.Template(resource_path='/com/usebottles/bottles/message-entry.ui')
class MessageEntry(Adw.ActionRow):
    __gtype_name__ = 'MessageEntry'

    # region Widgets
    btn_mark = Gtk.Template.Child()
    btn_details = Gtk.Template.Child()

    # endregion

    def __init__(self, nid, title, body, url, message_type, **kwargs):
        super().__init__(**kwargs)

        '''
        I found emojis a good way to represent the message type. But I'm not
        sure if it's a good idea to use in this case.
        '''
        icons = {
            "info": "📢",
            "warning": "⚠️",
            "error": "❌",
            "special": "⭐"
        }

        self.nid = nid
        self.url = url
        self.set_title(f"{icons[message_type]} {title}")
        self.set_subtitle(body)

        if url:
            self.btn_details.connect('clicked', self.__open_url)
            self.btn_details.set_visible(True)

        self.btn_mark.connect('clicked', self.__mark_as_read)

    def __open_url(self, widget):
        webbrowser.open(self.url)

    def __mark_as_read(self, widget):
        NotificationsManager().mark_as_read(self.nid)
        self.destroy()
