# generic.py
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

from gi.repository import Gtk, Pango

class MessageDialog(Gtk.MessageDialog):

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

        '''Display log as output if defined'''
        if log:
            message_scroll = Gtk.ScrolledWindow()
            message_scroll.set_hexpand(True)
            message_scroll.set_vexpand(True)

            message_view = Gtk.TextView()
            message_buffer = message_view.get_buffer()
            message_buffer.set_text(log)
            message_scroll.add(message_view)

        content = self.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(20)

        if log:
            box.add(message_scroll)

        content.add(box)
        self.show_all()


class Dialog(Gtk.Dialog):

    def __init__(self,
                 parent,
                 title=_("Warning"),
                 message=False,
                 log=False):

        Gtk.Dialog.__init__(self,
                            title=title,
                            parent=parent,
                            flags=Gtk.DialogFlags.USE_HEADER_BAR)

        '''Display log as output if defined'''
        if log:
            self.resize(600, 700)
            color = "#3e0622"
            if parent is not None and parent.settings.get_boolean("dark-theme"):
                color = "#d4036d"
            message_scroll = Gtk.ScrolledWindow()
            message_scroll.set_hexpand(True)
            message_scroll.set_vexpand(True)

            message_view = Gtk.TextView()
            message_buffer = message_view.get_buffer()
            buffer_iter = message_buffer.get_end_iter()
            message_buffer.insert_markup(
                buffer_iter, "<span foreground='%s'>%s</span>" % (color, log), -1)
            message_scroll.add(message_view)
        else:
            message_label = Gtk.Label(label=message)
            message_label.wrap_width = 500
            message_label.wrap_mode = Pango.WrapMode.WORD_CHAR

        content = self.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(20)

        if log:
            box.add(message_scroll)
        if message:
            box.add(message_label)

        content.add(box)
        self.show_all()

@Gtk.Template(resource_path='/com/usebottles/bottles/about.ui')
class AboutDialog(Gtk.AboutDialog):
    __gtype_name__ = 'AboutDialog'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
