#!/usr/bin/python3
'''
   Copyright 2017 Mirko Brombin (brombinmirko@gmail.com)

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

import os
import gi
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

        # Create welcome widget
        self.welcome = Granite.WidgetsWelcome()
        self.welcome = self.welcome.new(cn.App.application_name, cn.App.application_description)

        # Welcome voices
        self.welcome.append("insert-object", "New bottle", "Create a new wineprefix")
        self.welcome.append("gnome-mime-application-x-archive", "List bottles", "List all wineprefix")
        self.welcome.append("wine", "Manage wine", "Manage the wine installation")
        
        self.welcome.connect("activated", self.on_welcome_activated)

        self.add(self.welcome)

    def on_welcome_activated(self, widget, index):
        self.parent.parent.hbar.back.show()
        if index == 0:
            # Add wineprefix
            self.parent.parent.hbar.save.show()
            self.parent.stack.set_visible_child_name("create")
        elif index == 1:
            self.parent.parent.hbar.trash.show()
            self.parent.parent.hbar.properties.show()
            # List wineprefix
            self.parent.stack.set_visible_child_name("list")
        else:
            # List wineprefix
            self.parent.stack.set_visible_child_name("manage")
