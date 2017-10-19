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
import os
import locale
import gettext
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
except ImportError:
    import bottles.constants as cn
    import bottles.welcome as wl
    import bottles.create as cr
    import bottles.list as ls
    import bottles.detail as dt

class Stack(Gtk.Box):

    def __init__(self, parent):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.parent = parent

        try:
            current_locale, encoding = locale.getdefaultlocale()
            locale_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
            translate = gettext.translation ('bottles', locale_path, [current_locale] )
            _ = translate.gettext
        except FileNotFoundError:
            _ = str

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(1000)
        
        self.welcome = wl.Welcome(self)
        self.create = cr.Create(self)
        self.detail = dt.Detail(self)
        self.list_all = ls.List(self)

        self.stack.add_titled(self.welcome, "welcome", _('Welcome'))
        self.stack.add_titled(self.create, "create", _('Create'))
        self.stack.add_titled(self.detail, "detail", _('Detail'))
        self.stack.add_titled(self.list_all, "list", _('List'))

        self.pack_start(self.stack, True, True, 0)
