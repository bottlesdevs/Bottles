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


class BottlesMessageDialog(Gtk.MessageDialog):

    def __init__(self,
                 parent,
                 title=_("Warning"),
                 message=_("An error has occurred."),
                 log=False):

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
            message_buffer.set_text(log)
            message_scroll.add(message_view)

        content = self.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(20)

        if log: box.add(message_scroll)

        content.add(box)
        self.show_all()

class BottlesDialog(Gtk.Dialog):

    def __init__(self,
                 parent,
                 title=_("Warning"),
                 message=_("An error has occurred."),
                 log=False):

        Gtk.Dialog.__init__(self,
                            title=title,
                            parent=parent,
                            flags=Gtk.DialogFlags.USE_HEADER_BAR)

        '''
        If a log is passed, show it as an output
        '''
        if log:
            self.resize(600, 700)
            if parent.settings.get_boolean("dark-theme"):
                color = "#d4036d"
            else:
                color = "#3e0622"
            message_scroll = Gtk.ScrolledWindow()
            message_scroll.set_hexpand(True),message_scroll.set_vexpand(True)

            message_view = Gtk.TextView()
            message_buffer = message_view.get_buffer()
            iter = message_buffer.get_end_iter()
            message_buffer.insert_markup(
                iter, "<span foreground='%s'>%s</span>" % (color, log), -1)
            message_scroll.add(message_view)

        content = self.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(20)

        if log: box.add(message_scroll)

        content.add(box)
        self.show_all()

@Gtk.Template(resource_path='/com/usebottles/bottles/about.ui')
class BottlesAboutDialog(Gtk.AboutDialog):
    __gtype_name__ = 'BottlesAboutDialog'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()
