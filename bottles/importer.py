#!/usr/bin/python3
'''
    Copyright 2017 Mirko Brombin (send@mirko.pm)

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
from gi.repository import Gtk, Gdk, Granite, GdkPixbuf
try:
    import constants as cn
    import wine as w
except ImportError:
    import bottles.constants as cn
    import bottles.wine as w

class Importer(Gtk.Box):
    status = False

    try:
        current_locale, encoding = locale.getdefaultlocale()
        locale_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
        translate = gettext.translation (cn.App.application_shortname, locale_path, [current_locale] )
        _ = translate.gettext
    except FileNotFoundError:
        _ = str

    def __init__(self, parent):
        Gtk.Box.__init__(self, False, 0)
        self.wine = w.Wine(self)
        self.parent = parent
        self.set_name("WineImporter")

        self.set_orientation(Gtk.Orientation.VERTICAL)

        self.num = 0
        self.description = Gtk.Label()
        self.description.set_name('WineDescription')
        self.description.set_justify(Gtk.Justification.CENTER)
        self.add(self.description)
        self.generate_entries()
        
    def generate_entries(self, update=False):
        bottles = self.wine.list_POLs()
        self.description.set_label(self._('I found %d wineprefixes from PlayOnLinux' % len(bottles)))
        if update == False:
            self.wine_model = Gtk.ListStore(str, str, str, str)
        self.wine_model.clear()
        for wine_l in bottles:
            self.wine_model.append([wine_l[0], wine_l[1], wine_l[2], wine_l[3]])
        self.bottles_sort = Gtk.TreeModelSort(model=self.wine_model)
        self.treeview = Gtk.TreeView.new_with_model(self.bottles_sort)
        tree_selection = self.treeview.get_selection()
        tree_selection.connect('changed', self.on_row_change)
        for i, column_title in enumerate(["Name", "Arch", "Version", "Size"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)
        self.add(self.treeview)
        
    def on_row_change(self, widget):
        (model, pathlist) = widget.get_selected_rows()
        for path in pathlist :
            tree_iter = model.get_iter(path)
            self.parent.parent.hbar.POL_name = model.get_value(tree_iter,0)
            self.parent.parent.hbar.POL_arch = model.get_value(tree_iter,1)

