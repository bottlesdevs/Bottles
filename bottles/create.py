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
from gi.repository import Gtk, Gdk, Granite, GdkPixbuf
try:
    import constants as cn
    import wine as w
except ImportError:
    import bottles.constants as cn
    import bottles.wine as w

class Create(Gtk.Box):
    status = False

    def __init__(self, parent):
        Gtk.Box.__init__(self, False, 0)
        self.wine = w.Wine(self)
        self.parent = parent

        self.set_border_width(80)
        #win.resize(800,400)
        self.set_orientation(Gtk.Orientation.VERTICAL)

        title = Gtk.Label("New bottle")
        title.set_name('WineTitle')
        title.set_justify(Gtk.Justification.CENTER)
        self.add(title)

        description = Gtk.Label("Here you can create a new bottle")
        description.set_name('WineDescription')
        description.set_justify(Gtk.Justification.CENTER)
        self.add(description)

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_spacing(4)
        self.add(self.grid)
        
        prefix_name = Gtk.Label("Bottle name")
        prefix_arch = Gtk.Label("Type (32/64)")
        #prefix_wine = Gtk.Label("Wine version")

        self.entry_name = Gtk.Entry()
        self.entry_name.set_placeholder_text("Microsoft Office")
        #entry_name.connect("key-release-event", self.on_entry_name_key_release)
        #entry_name.connect("activate", self.on_entry_name_activate)

        self.arch_store = Gtk.ListStore(int, str)
        self.arch_store.append([0, "32 Bit"])
        self.arch_store.append([1, "64 Bit"])
        self.entry_arch = Gtk.ComboBox.new_with_model_and_entry(self.arch_store)
        self.entry_arch.set_entry_text_column(1)
        self.entry_arch.set_active(0)

        '''self.wine_store = Gtk.ListStore(GdkPixbuf.Pixbuf, int, str)
        for r in self.wine.list_releases("32"):
            self.wine_store.append(r)
        self.entry_wine = Gtk.ComboBox.new_with_model_and_entry(self.wine_store)
        self.entry_wine.set_entry_text_column(2)
        self.entry_wine.set_active(0)
        entry_wine_pix_render = Gtk.CellRendererPixbuf()
        self.entry_wine.pack_start(entry_wine_pix_render, False)
        self.entry_wine.add_attribute(entry_wine_pix_render, "pixbuf", 0)'''

        self.grid.add(prefix_name)
        self.grid.attach(self.entry_name, 1, 0, 2, 1)
        self.grid.attach_next_to(prefix_arch, prefix_name, Gtk.PositionType.BOTTOM, 1, 2)
        self.grid.attach_next_to(self.entry_arch, prefix_arch, Gtk.PositionType.RIGHT, 2, 1)
        '''self.grid.attach_next_to(prefix_wine, prefix_arch, Gtk.PositionType.BOTTOM, 1, 2)
        self.grid.attach_next_to(self.entry_wine, prefix_wine, Gtk.PositionType.RIGHT, 2, 1)'''

    '''def on_entry_key_release(self, entry, ev, data=None):
        url = entry.get_text()
        self.ppa.validate(url, self.validate)

    def on_entry_activate(self, entry):
        if self.status:
            self.ppa.add()'''
