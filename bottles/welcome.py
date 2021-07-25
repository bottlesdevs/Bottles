#!/usr/bin/python3
'''
    Copyright 2017 Mirko Brombin (send@mirko.pm)

    This file is part of Bottles.

    Bottles is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Bottles is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Bottles.  If not, see <http://www.gnu.org/licenses/>.
'''

import gi
import os
import locale
import gettext
import webbrowser
gi.require_version('Gtk', '3.0')
gi.require_version('Granite', '1.0')
from gi.repository import Gtk, Gdk, Granite
try:
    import constants as cn
except ImportError:
    import bottles.constants as cn

class Welcome(Gtk.Box):

    def __init__(self, parent):
        Gtk.Box.__init__(self, False, 0)
        self.parent = parent
        self.set_orientation(Gtk.Orientation.VERTICAL)

        v3_infobar = Gtk.InfoBar()
        v3_infobar.set_show_close_button(False)
        v3_buttonbox = Gtk.ButtonBox()
        v3_link = Gtk.Button(label="Information")
        v3_link.message_type = Gtk.MessageType.INFO
        v3_link.connect("clicked", self.go_to_v3)
        v3_buttonbox.add(v3_link)
        v3_infobar.get_content_area().add(Gtk.Label("Bottles 3 (Treviso) is out!"))
        v3_infobar.get_content_area().add(v3_buttonbox)
        self.add(v3_infobar)

        try:
            current_locale, encoding = locale.getdefaultlocale()
            locale_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
            translate = gettext.translation (cn.App.application_shortname, locale_path, [current_locale] )
            _ = translate.gettext
        except FileNotFoundError:
            _ = str

        # Create welcome widget
        self.welcome = Granite.WidgetsWelcome()
        self.welcome = self.welcome.new(cn.App.application_name, cn.App.application_description)

        # Welcome voices
        self.welcome.append("list-add-symbolic", _('New bottle'), _('Create a new bottle'))
        self.welcome.append("folder-download-symbolic", _('Import and convert'), _('Import a third-party wineprefix'))
        self.welcome.append("preferences-desktop-apps-symbolic", _('List bottles'), _('List all bottles'))
        
        self.welcome.connect("activated", self.on_welcome_activated)

        self.add(self.welcome)
    
    def go_to_v3(self, infobar):
        webbrowser.open_new_tab("https://usebottles.com")

    def on_welcome_activated(self, widget, index):
        self.parent.parent.hbar.back.show()
        if index == 0:
            # Add wineprefix
            self.parent.parent.hbar.save.show()
            self.parent.stack.set_visible_child_name("create")
        elif index == 1:
            # Import wineprefix
            self.parent.parent.hbar.convert.show()
            self.parent.stack.set_visible_child_name("importer")
        else:
            self.parent.parent.hbar.trash.show()
            self.parent.parent.hbar.properties.show()
            self.parent.parent.hbar.refresh.show()
            # List wineprefix
            self.parent.stack.set_visible_child_name("list")

