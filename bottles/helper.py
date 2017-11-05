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

class shell_colors:
    HEADER = '\033[95m'
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    NORMAL = '\033[98m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

class HLog:
    def title(str):
        print (shell_colors.HEADER + shell_colors.BOLD + "=== " + str + " ===" + shell_colors.END)

    def text(str):
        print (shell_colors.NORMAL + str + shell_colors.END)

    def info(str):
        print (shell_colors.INFO + shell_colors.BOLD + str + shell_colors.END)

    def bold(str):
        print (shell_colors.NORMAL + shell_colors.BOLD + str + shell_colors.END)

    def success(str):
        print (shell_colors.SUCCESS + shell_colors.BOLD + str + shell_colors.END)

    def error(str):
        print (shell_colors.ERROR + shell_colors.BOLD + "Error: " + str + shell_colors.END)

    def warning(str):
        print (shell_colors.WARNING + shell_colors.BOLD + str + shell_colors.END)
