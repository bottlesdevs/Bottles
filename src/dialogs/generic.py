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

import gi

gi.require_version('GtkSource', '4')

from gi.repository import Gtk, GtkSource, Gdk, Handy, Pango, WebKit2
from gettext import gettext as _


class MessageDialog(Gtk.MessageDialog):

    def __init__(
            self,
            parent,
            title=_("Warning"),
            message=_("An error has occurred."),
            log=False
    ):

        Gtk.MessageDialog.__init__(
            self,
            parent=parent,
            flags=Gtk.DialogFlags.USE_HEADER_BAR,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_format=message
        )

        content = self.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(20)

        if log:
            # display log as output if defined
            message_scroll = Gtk.ScrolledWindow()
            message_scroll.set_hexpand(True)
            message_scroll.set_vexpand(True)

            message_view = Gtk.TextView()
            message_buffer = message_view.get_buffer()
            message_buffer.set_text(log)
            message_scroll.add(message_view)

            box.add(message_scroll)

        content.add(box)
        self.show_all()


class SourceDialog(Handy.Window):

    def __init__(self, parent, title, message, buttons=None, **kwargs):
        super().__init__(**kwargs)
        if buttons is None:
            buttons = []

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(700, 700)

        self.parent = parent
        self.title = title
        self.message = message
        self.buttons = buttons

        self.__build_ui()

    def __build_ui(self):
        headerbar = Handy.HeaderBar()
        btn_copy = Gtk.Button.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.BUTTON)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        style_scheme_manager = GtkSource.StyleSchemeManager.get_default()
        lang_manager = GtkSource.LanguageManager.get_default()
        source_buffer = GtkSource.Buffer(
            highlight_syntax=True,
            highlight_matching_brackets=True,
            style_scheme=style_scheme_manager.get_scheme("oblivion"),
            language=lang_manager.get_language("yaml")
        )
        source_view = GtkSource.View(
            buffer=source_buffer,
            show_line_numbers=True,
            show_line_marks=True,
            tab_width=4,
            monospace=True
        )
        source_buffer = source_view.get_buffer()

        headerbar.set_show_close_button(True)
        headerbar.set_title(self.title)
        headerbar.pack_end(btn_copy)

        btn_copy.connect("clicked", self.__copy_text)
        btn_copy.set_tooltip_text(_("Copy to clipboard"))

        for button in self.buttons:
            _btn = Gtk.Button.new_from_icon_name(button["icon"], Gtk.IconSize.BUTTON)
            _btn.connect("clicked", button["callback"])
            _btn.set_tooltip_text(button["tooltip"])
            headerbar.pack_end(_btn)

        buffer_iter = source_buffer.get_end_iter()
        source_buffer.insert(buffer_iter, self.message)
        scrolled.add(source_view)

        box.add(headerbar)
        box.add(scrolled)

        self.add(box)
        self.show_all()

    def __copy_text(self, widget):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self.message, -1)


class TextDialog(Handy.Window):

    def __init__(self, parent, title, message, **kwargs):
        super().__init__(**kwargs)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(700, 700)

        self.parent = parent
        self.title = title
        self.message = message

        self.__build_ui()

    def __build_ui(self):
        headerbar = Handy.HeaderBar()
        btn_copy = Gtk.Button.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.BUTTON)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        textview = Gtk.TextView()
        textbuffer = textview.get_buffer()

        headerbar.set_show_close_button(True)
        headerbar.set_title(self.title)
        headerbar.pack_end(btn_copy)

        btn_copy.connect("clicked", self.__copy_text)
        btn_copy.set_tooltip_text(_("Copy to clipboard"))

        buffer_iter = textbuffer.get_end_iter()
        textbuffer.insert(buffer_iter, self.message)
        scrolled.add(textview)

        box.add(headerbar)
        box.add(scrolled)

        self.add(box)
        self.show_all()

    def __copy_text(self, widget):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self.message, -1)


class WebDialog(Handy.Window):

    def __init__(self, parent, title, message):
        Handy.Window.__init__(self, title=title)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(700, 700)
        self.set_transient_for(parent)
        self.set_modal(True)

        self.parent = parent
        self.title = title
        self.message = message

        self.__build_ui()

    def __build_ui(self):
        headerbar = Handy.HeaderBar()
        btn_copy = Gtk.Button.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.BUTTON)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        webview = WebKit2.WebView()

        headerbar.set_show_close_button(True)
        headerbar.set_title(self.title)
        headerbar.pack_end(btn_copy)

        btn_copy.connect("clicked", self.__copy_text)
        btn_copy.set_tooltip_text(_("Copy to clipboard"))

        webview.load_html(self.message, "file://")
        scrolled.add(webview)

        box.add(headerbar)
        box.add(scrolled)

        self.add(box)
        self.show_all()

    def __copy_text(self, widget):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self.message, -1)


class Dialog(Gtk.Dialog):

    def __init__(
            self,
            parent,
            title=_("Warning"),
            message=False,
            log=False,
            html=False
    ):

        Gtk.Dialog.__init__(
            self,
            title=title,
            parent=parent,
            flags=Gtk.DialogFlags.USE_HEADER_BAR
        )

        content = self.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(20)

        if log or html:
            '''
            If log is defined, display it as output, also change the
            the foreground according to the user preferences.
            '''
            is_dark = Handy.StyleManager.get_default().get_dark()

            self.resize(600, 700)
            color = "#3e0622"

            message_scroll = Gtk.ScrolledWindow()
            message_scroll.set_hexpand(True)
            message_scroll.set_vexpand(True)

            if log:
                message_view = Gtk.TextView()
                message_buffer = message_view.get_buffer()
                buffer_iter = message_buffer.get_end_iter()
                for l in log.split("\n"):
                    message_buffer.insert_markup(
                        buffer_iter,
                        f"<span foreground='{color}'>{l}</span>\n",
                        -1
                    )
                message_scroll.add(message_view)
                box.add(message_scroll)

            elif html:
                ucntm = WebKit2.UserContentManager()
                if is_dark:
                    stylesheet = WebKit2.UserStyleSheet(
                        "body { color: #fff; background-color: #242424; }",
                        WebKit2.UserContentInjectedFrames.TOP_FRAME,
                        WebKit2.UserStyleLevel.USER,
                        None, None
                    )
                    ucntm.add_style_sheet(stylesheet)
                webview = WebKit2.WebView(
                    user_content_manager=ucntm
                )
                webview.load_html(html, "file://")
                message_scroll.add(webview)
                box.add(message_scroll)

        elif message:
            message_label = Gtk.Label(label=message)
            message_label.wrap_width = 500
            message_label.wrap_mode = Pango.WrapMode.WORD_CHAR
            box.add(message_label)

        content.add(box)
        self.show_all()


@Gtk.Template(resource_path='/com/usebottles/bottles/about.ui')
class AboutDialog(Gtk.AboutDialog):
    __gtype_name__ = 'AboutDialog'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def do_response(self, response_id):
        if response_id == Gtk.ResponseType.DELETE_EVENT:
            self.destroy()
