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
from gi.repository import Gtk, Gdk, Gio
try:
    import constants as cn
    import wine as w
    import helper as hl
except ImportError:
    import bottles.constants as cn
    import bottles.wine as w
    import bottles.helper as hl

class Headerbar(Gtk.HeaderBar):
    bottle_name = ""
    POL_name = ""
    POL_arch = ""

    def __init__(self, parent):
        Gtk.HeaderBar.__init__(self)
        self.parent = parent
        self.wine = w.Wine(self)
        self.HGtk = hl.HGtk()
        self.set_name("WineHeaderbar")

        locale_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')

        try:
            current_locale, encoding = locale.getdefaultlocale()
            translate = gettext.translation (cn.App.application_shortname, locale_path, [current_locale] )
            _ = translate.gettext
        except FileNotFoundError:
            _ = str

        self.set_show_close_button(True)
        self.props.title = cn.App.application_name

        # help button
        # self.help = Gtk.Button.new_from_icon_name("help-contents", Gtk.IconSize.LARGE_TOOLBAR)
        # self.help.connect("clicked", self.on_help_clicked)
        # self.pack_end(self.help)

        # trash button
        self.trash = Gtk.Button()
        self.trash = Gtk.Button.new_from_icon_name("edit-delete", Gtk.IconSize.LARGE_TOOLBAR)
        self.trash.connect("clicked", self.on_trash_clicked)
        self.pack_end(self.trash)

        # properties button
        self.properties = Gtk.Button()
        self.properties = Gtk.Button.new_from_icon_name("document-properties", Gtk.IconSize.LARGE_TOOLBAR)
        self.properties.connect("clicked", self.on_properties_clicked)
        self.pack_end(self.properties)

        # save button
        self.save = Gtk.Button(_('Save'))
        self.save.connect("clicked", self.on_save_clicked)
        self.HGtk.add_class(self.save, "suggested-action")
        self.pack_end(self.save)

        # start button
        # self.start = Gtk.Button()
        # self.start = Gtk.Button.new_from_icon_name("applications-other", Gtk.IconSize.LARGE_TOOLBAR)
        # self.start.connect("clicked", self.on_start_clicked)
        # self.pack_end(self.start)

        # convert button
        self.convert = Gtk.Button()
        self.convert = Gtk.Button.new_from_icon_name("document-import", Gtk.IconSize.LARGE_TOOLBAR)
        self.convert.connect("clicked", self.on_convert_clicked)
        self.pack_end(self.convert)

        # refresh button
        self.refresh = Gtk.Button()
        self.refresh = Gtk.Button.new_from_icon_name("view-refresh", Gtk.IconSize.LARGE_TOOLBAR)
        self.refresh.connect("clicked", self.on_refresh_clicked)
        self.pack_end(self.refresh)

        # spinner button
        self.spinner = Gtk.Spinner()
        self.pack_end(self.spinner)

        # back button
        self.back = Gtk.Button(_('Return'))
        self.back.connect("clicked", self.on_back_clicked)
        Gtk.StyleContext.add_class(self.back.get_style_context(), "back-button")
        self.pack_start(self.back)
    
    def on_trash_clicked(self, widget):
        self.wine.remove_bottle(self.bottle_name)
    
    def on_properties_clicked(self, widget):
        self.refresh.hide()
        self.wine.detail_bottle(self.bottle_name)
    
    def on_save_clicked(self, widget):
        d = self.parent.stack.create
        name = d.entry_name.get_text()
        arch = d.entry_arch.get_active_iter()
        #wine = d.entry_wine.get_active_iter()
        arch = d.arch_store[arch][1]
        #wine = d.wine_store[wine][2]
        self.wine.create_bottle(name, arch)

    def on_back_clicked(self, widget):
        self.props.title = cn.App.application_name
        self.back.hide()
        self.save.hide()
        self.trash.hide()
        self.properties.hide() 
        self.convert.hide()
        self.refresh.hide()
        self.parent.stack.stack.set_visible_child_name("welcome")

    def on_start_clicked(self, widget):
        pass

    def on_convert_clicked(self, widget):
        self.wine.convert_POL(self.POL_name, self.POL_arch)
    
    def on_refresh_clicked(self, widget):
        self.parent.stack.list_all.generate_entries(True)

