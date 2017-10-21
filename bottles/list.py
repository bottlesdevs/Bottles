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
    import wine as w
except ImportError:
    import bottles.constants as cn
    import bottles.wine as w

class List(Gtk.ScrolledWindow):

    def __init__(self, parent):
        Gtk.ScrolledWindow.__init__(self)
        self.parent = parent
        self.wine = w.Wine(self)
        self.generate_entries()
        self.set_name("WineList")
        
    def generate_entries(self, update=False):
        bottles = self.wine.list_bottles()
        if update == False:
            self.wine_model = Gtk.ListStore(str)
        self.wine_model.clear()
        for wine_l in bottles:
            self.wine_model.append([wine_l])
        self.bottles_sort = Gtk.TreeModelSort(model=self.wine_model)
        self.treeview = Gtk.TreeView.new_with_model(self.bottles_sort)
        tree_selection = self.treeview.get_selection()
        tree_selection.connect('changed', self.on_row_change)
        for i, column_title in enumerate(["Name"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)
        self.add(self.treeview)
        
    def on_row_change(self, widget):
        (model, pathlist) = widget.get_selected_rows()
        for path in pathlist :
            tree_iter = model.get_iter(path)
            value = model.get_value(tree_iter,0)
            self.parent.parent.hbar.bottle_name = value
