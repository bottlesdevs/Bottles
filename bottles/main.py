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
gi.require_version('Gtk', '3.0')
gi.require_version('Granite', '1.0')
from gi.repository import Gtk, Gdk, Granite, GObject
try:
    import constants as cn
    import window as wn
    import wine as w
except ImportError:
    import bottles.constants as cn
    import bottles.window as wn
    import bottles.wine as w

class Application(Granite.Application):

    def do_activate(self):
        self.win = wn.Window()
        self.wine = w.Wine(self.win)
        self.wine.check_work_dir()
        self.win.set_default_size(750, 650) 
        self.win.connect("delete-event", Gtk.main_quit)
        self.win.show_all()
        self.win.hbar.back.hide()
        self.win.hbar.save.hide()
        self.win.hbar.trash.hide()
        self.win.hbar.properties.hide()

        Gtk.main()

app = Application()

app.run("", 1)
