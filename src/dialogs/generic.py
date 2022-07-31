# generic.py
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

from gi.repository import Gtk, GtkSource, Gdk, Adw
from gettext import gettext as _


class MessageDialog(Gtk.MessageDialog):

    def __init__(self, window, message=_("An error has occurred."), log=False):
        Gtk.MessageDialog.__init__(
            self,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=message
        )
        self.set_transient_for(window)
        self.set_modal(True)

        if log:
            # display log as output if defined
            message_scroll = Gtk.ScrolledWindow()
            message_scroll.set_hexpand(True)
            message_scroll.set_vexpand(True)

            message_view = Gtk.TextView()
            message_view.get_buffer().set_text(log)
            message_scroll.append(message_view)

            self.message_area.append(message_scroll)


class SourceDialog(Adw.Window):

    def __init__(self, parent, title, message, buttons=None, lang="yaml", **kwargs):
        super().__init__(**kwargs)
        if buttons is None:
            buttons = []

        self.set_default_size(700, 700)

        self.parent = parent
        self.title = title
        self.message = message
        self.buttons = buttons
        self.lang = lang

        self.__build_ui()

    def __build_ui(self):
        headerbar = Gtk.HeaderBar()
        btn_copy = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        style_scheme_manager = GtkSource.StyleSchemeManager.get_default()
        lang_manager = GtkSource.LanguageManager.get_default()
        source_buffer = GtkSource.Buffer(
            highlight_syntax=True,
            highlight_matching_brackets=True,
            style_scheme=style_scheme_manager.get_scheme("oblivion"),
            language=lang_manager.get_language(self.lang)
        )
        source_view = GtkSource.View(
            buffer=source_buffer,
            show_line_numbers=True,
            show_line_marks=True,
            tab_width=4,
            monospace=True
        )
        source_buffer = source_view.get_buffer()

        headerbar.set_title_widget(Gtk.Label.new(self.title))
        headerbar.pack_end(btn_copy)

        btn_copy.connect("clicked", self.__copy_text)
        btn_copy.set_tooltip_text(_("Copy to clipboard"))

        for button in self.buttons:
            _btn = Gtk.Button.new_from_icon_name(button["icon"])
            _btn.connect("clicked", button["callback"])
            _btn.set_tooltip_text(button["tooltip"])
            headerbar.pack_end(_btn)

        buffer_iter = source_buffer.get_end_iter()
        source_buffer.insert(buffer_iter, self.message)
        scrolled.set_child(source_view)

        box.append(headerbar)
        box.append(scrolled)

        self.set_content(box)

    def __copy_text(self, widget):
        clipboard = Gdk.Display.get_clipboard(Gdk.Display.get_default())
        clipboard.set_content(Gdk.ContentProvider.new_for_value(self.message))


class TextDialog(Adw.Window):

    def __init__(self, parent, title, message, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(700, 700)

        self.parent = parent
        self.title = title
        self.message = message

        self.__build_ui()

    def __build_ui(self):
        headerbar = Adw.HeaderBar()
        btn_copy = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        textview = Gtk.TextView()
        textbuffer = textview.get_buffer()

        headerbar.set_title_widget(Gtk.Label.new(self.title))
        headerbar.pack_end(btn_copy)

        btn_copy.connect("clicked", self.__copy_text)
        btn_copy.set_tooltip_text(_("Copy to clipboard"))

        buffer_iter = textbuffer.get_end_iter()
        textbuffer.insert(buffer_iter, self.message)
        scrolled.set_child(textview)

        box.append(headerbar)
        box.append(scrolled)

        self.set_content(box)

    def __copy_text(self, widget):
        clipboard = Gdk.Display.get_clipboard(Gdk.Display.get_default())
        clipboard.set_content(Gdk.ContentProvider.new_for_value(self.message))


class WebDialog(Adw.Window):
    """
    TODO: currently unused, waiting for webkit2gtk-5 to be released with the GNOME Runtime
          use SourceDialog or TextDialog in the meantime
    """

    def __init__(self, parent, title, message):
        Adw.Window.__init__(self, title=title)
        self.set_default_size(700, 700)
        self.set_transient_for(parent)
        self.set_modal(True)

        self.parent = parent
        self.title = title
        self.message = message

        self.__build_ui()

    def __build_ui(self):
        headerbar = Adw.HeaderBar()
        btn_copy = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        # webview = WebKit2.WebView()

        headerbar.set_title_widget(Gtk.Label.new(self.title))
        headerbar.pack_end(btn_copy)

        btn_copy.connect("clicked", self.__copy_text)
        btn_copy.set_tooltip_text(_("Copy to clipboard"))

        webview.load_html(self.message, "file://")
        # scrolled.append(webview)

        box.append(headerbar)
        box.append(scrolled)

        self.set_content(box)

    def __copy_text(self, widget):
        clipboard = Gdk.Display.get_clipboard(Gdk.Display.get_default())
        clipboard.set_content(Gdk.ContentProvider.new_for_value(self.message))

