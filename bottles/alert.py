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
import threading
import subprocess
import shutil
import time
from pathlib import Path
import webbrowser
gi.require_version('Gtk', '3.0')
gi.require_version('Granite', '1.0')
from gi.repository import Gtk, Gdk, Granite, GObject, GLib, GdkPixbuf
try:
    import constants as cn
    import helper as hl
except ImportError:
    import bottles.constants as cn
    import bottles.helper as hl

class Alert(Gtk.Dialog):

    def __init__(self, window, text, width, height):
        Gtk.Dialog.__init__(self, "Bottle:Error", window, 0,(Gtk.STOCK_OK, Gtk.ResponseType.OK))

        self.set_default_size(width, height)

        label = Gtk.Label(text)
        box = self.get_content_area()
        box.add(label)
        self.show_all()
