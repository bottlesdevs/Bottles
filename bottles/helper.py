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

# TODO: In this class I will try to create a simpler wrapper for Gtk methods
class HGtk:
    settings = Gtk.Settings.get_default()

    def remove_class(self, widget, css_class):
        Gtk.StyleContext.remove_class(widget.get_style_context(), css_class)

    def add_class(self, widget, css_class):
        Gtk.StyleContext.add_class(widget.get_style_context(), css_class)

    def set_dark_mode(self, status=0):
        self.settings.set_property("gtk-application-prefer-dark-theme", status)
