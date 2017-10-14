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
    import welcome as wl
    import create as cr
    import list as ls
    import detail as dt
    import manage as mn
except ImportError:
    import bottles.constants as cn
    import bottles.welcome as wl
    import bottles.create as cr
    import bottles.list as ls
    import bottles.detail as dt
    import bottles.manage as mn

class Stack(Gtk.Box):

    def __init__(self, parent):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.parent = parent

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(1000)
        
        self.welcome = wl.Welcome(self)
        self.create = cr.Create(self)
        self.detail = dt.Detail(self)
        self.list_all = ls.List(self)
        self.manage = mn.Manage(self)

        self.stack.add_titled(self.welcome, "welcome", "Welcome")
        self.stack.add_titled(self.create, "create", "Create")
        self.stack.add_titled(self.detail, "detail", "Detail")
        self.stack.add_titled(self.list_all, "list", "List")
        self.stack.add_titled(self.manage, "manage", "Manage")

        self.pack_start(self.stack, True, True, 0)
