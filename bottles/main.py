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
import locale
import gettext
import argparse
gi.require_version('Gtk', '3.0')
gi.require_version('Granite', '1.0')
from gi.repository import Gtk, Gio, Gdk, Granite, GObject
try:
    import constants as cn
    import window as wn
    import wine as w
    import helper as hl
except ImportError:
    import bottles.constants as cn
    import bottles.window as wn
    import bottles.wine as w
    import bottles.helper as hl

HLog = hl.HLog

try:
    current_locale, encoding = locale.getdefaultlocale()
    locale_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
    translate = gettext.translation (cn.App.application_shortname, locale_path, [current_locale] )
    _ = translate.gettext
except FileNotFoundError:
    _ = str

HLog.title(_('Starting Bottles'))
HLog.bold(_('Build Version: %s' % cn.App.application_version))
HLog.bold(_('Wine Version: %s' % w.Wine.get_wine_version()))
HLog.bold(_('Wiki: %s' % cn.App.help_url))

class Application(Gtk.Application):

    def do_activate(self):

        self.win = wn.Window()

        self.wine = w.Wine(self.win)
        self.wine.check_work_dir()

        self.win.set_default_size(550, 600) 
        self.win.set_resizable(False)
        self.win.connect("delete-event", Gtk.main_quit)

        parser = argparse.ArgumentParser(description = cn.App.application_description)
        parser.add_argument('--about', action='store_true', help='About '+cn.App.application_name)
        args = parser.parse_args()  
        if args.about == True:
            self.show_about(self.win)
        else:
            self.win.show_all()
            self.win.hbar.back.hide()
            self.win.hbar.save.hide()
            self.win.hbar.trash.hide()
            self.win.hbar.properties.hide()
            self.win.hbar.convert.hide()
            self.win.hbar.refresh.hide()

        Gtk.main()

app = Application()

stylesheet = """
    @define-color colorPrimary """+cn.Colors.primary_color+""";
    @define-color textColorPrimary """+cn.Colors.primary_text_color+""";
    @define-color textColorPrimaryShadow """+cn.Colors.primary_text_shadow_color+""";
""";

style_provider = Gtk.CssProvider()
style_provider.load_from_data(bytes(stylesheet.encode()))
Gtk.StyleContext.add_provider_for_screen(
    Gdk.Screen.get_default(), style_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
)

app.application_id = cn.App.application_id
app.flags = Gio.ApplicationFlags.FLAGS_NONE
app.program_name = cn.App.application_name
app.build_version = cn.App.application_version
app.about_documenters = cn.App.about_documenters
app.about_authors = cn.App.about_authors
app.about_comments = cn.App.about_comments
app.app_years = cn.App.app_years
app.build_version = cn.App.application_version;
app.app_icon = cn.App.application_id
app.main_url = cn.App.main_url
app.bug_url = cn.App.bug_url
app.help_url = cn.App.help_url
app.translate_url = cn.App.translate_url

app.run("")
