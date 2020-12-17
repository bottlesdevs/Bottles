# dialog.py
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


class BottlesDialog(Gtk.MessageDialog):

    def __init__(self,
                 parent,
                 title="Warning",
                 message="An error has occurred.",
                 log=False,
                 log_exception=False):

        Gtk.MessageDialog.__init__(self,
                            parent=parent,
                            flags=Gtk.DialogFlags.USE_HEADER_BAR,
                            type=Gtk.MessageType.WARNING,
                            buttons=Gtk.ButtonsType.OK_CANCEL,
                            message_format=message)

        '''
        If a log is passed, show it as an output
        '''
        if log:
            message_scroll = Gtk.ScrolledWindow()
            message_scroll.set_hexpand(True),message_scroll.set_vexpand(True)

            message_view = Gtk.TextView()
            message_buffer = message_view.get_buffer()
            message_buffer.set_text(log_exception)
            message_scroll.add(message_view)

        content = self.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(20)

        if log: box.add(message_scroll)

        content.add(box)
        self.show_all()

@Gtk.Template(resource_path='/pm/mirko/bottles/about.ui')
class BottlesAboutDialog(Gtk.AboutDialog):
    __gtype_name__ = 'BottlesAboutDialog'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()
