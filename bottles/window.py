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

import gi
from datetime import datetime
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
try:
    import constants as cn
    import headerbar as hb
    import helper as hl
    import stack as sk
except ImportError:
    import bottles.constants as cn
    import bottles.headerbar as hb
    import bottles.helper as hl
    import bottles.stack as sk

class Window(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title=cn.App.application_name)

        self.hbar = hb.Headerbar(self)
        self.set_titlebar(self.hbar)

        HGtk = hl.HGtk()
        HGtk.set_dark_mode(1)

        self.stack = sk.Stack(self)
        self.add(self.stack)

        self.screen = Gdk.Screen.get_default()
        self.css_provider = Gtk.CssProvider()

        try:
            self.css_provider.load_from_path('../data/style.css')
        except GLib.Error:
            self.css_provider.load_from_path('/usr/local/bin/bottles/style.css')
        except GLib.Error:
            self.css_provider.load_from_path('/usr/bin/bottles/style.css')
        except GLib.Error:
            print('Couldn\'t load style.css')
            exit(1)

        self.context = Gtk.StyleContext()
        self.context.add_provider_for_screen(self.screen, self.css_provider,
          Gtk.STYLE_PROVIDER_PRIORITY_USER)
