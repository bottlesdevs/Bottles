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
import os
import locale
import gettext
import subprocess
import webbrowser
gi.require_version('Gtk', '3.0')
gi.require_version('Granite', '1.0')
from gi.repository import Gtk, Gdk, Granite, GdkPixbuf
try:
    import constants as cn
    import wine as w
    import helper as hl
except ImportError:
    import bottles.constants as cn
    import bottles.wine as w
    import bottles.helper as hl

class Detail(Gtk.Box):
    status = False
    working_dir = ""

    def __init__(self, parent):
        Gtk.Box.__init__(self, False, 0)
        self.wine = w.Wine(self)
        self.parent = parent
        HGtk = hl.HGtk

        try:
            current_locale, encoding = locale.getdefaultlocale()
            locale_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
            translate = gettext.translation (cn.App.application_shortname, locale_path, [current_locale] )
            _ = translate.gettext
        except FileNotFoundError:
            _ = str

        self._ = _

        self.set_border_width(20)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_name("WineDetail")

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(self.vbox)
        
        self.grid_1 = Gtk.Grid()
        self.grid_1.set_column_homogeneous(True)
        self.grid_1.set_column_spacing(20)
        self.vbox.add(self.grid_1)

        # Drive C
        self.button_drive_c = Gtk.Button.new_from_icon_name("folder", Gtk.IconSize.DIALOG)
        self.button_drive_c.connect("clicked", self.on_button_drive_c_clicked)
        self.grid_1.add(self.button_drive_c)
        
        # Winecfg
        self.button_wine_cfg = Gtk.Button.new_from_icon_name("bottles_wine-winecfg", Gtk.IconSize.DIALOG)
        self.button_wine_cfg.connect("clicked", self.on_button_wine_cfg_clicked)
        self.grid_1.add(self.button_wine_cfg)
        
        # Winetricks
        self.button_winetricks = Gtk.Button.new_from_icon_name("bottles_winetricks", Gtk.IconSize.DIALOG)
        self.button_winetricks.connect("clicked", self.on_button_winetricks_clicked)
        self.grid_1.add(self.button_winetricks)
        
        grid_2 = Gtk.Grid()
        grid_2.set_column_spacing(20)
        grid_2.set_column_homogeneous(True)
        self.vbox.add(grid_2)

        label_drive_c = Gtk.Label(_('Browse C:'))
        HGtk.add_class(self, label_drive_c, "label_cell")
        grid_2.add(label_drive_c)

        label_wine_cfg = Gtk.Label(_('Configure'))
        HGtk.add_class(self, label_wine_cfg, "label_cell")
        grid_2.add(label_wine_cfg)

        label_winetricks = Gtk.Label(_('Winetricks'))
        HGtk.add_class(self, label_winetricks, "label_cell")
        grid_2.add(label_winetricks)
        
        self.grid_3 = Gtk.Grid()
        self.grid_3.set_column_spacing(20)
        self.grid_3.set_column_homogeneous(True)
        self.vbox.add(self.grid_3)
        
        # Terminal
        self.button_terminal = Gtk.Button.new_from_icon_name("utilities-terminal", Gtk.IconSize.DIALOG)
        self.button_terminal.connect("clicked", self.on_button_terminal_clicked)
        self.grid_3.add(self.button_terminal)
        
        # Monitor
        self.button_monitor = Gtk.Button.new_from_icon_name("utilities-system-monitor", Gtk.IconSize.DIALOG)
        self.button_monitor.connect("clicked", self.on_button_monitor_clicked)
        self.grid_3.add(self.button_monitor)
        
        # Settings
        self.button_settings = Gtk.Button.new_from_icon_name("preferences-desktop", Gtk.IconSize.DIALOG)
        self.button_settings.connect("clicked", self.on_button_settings_clicked)
        self.grid_3.add(self.button_settings)

        grid_4 = Gtk.Grid()
        grid_4.set_column_spacing(20)
        grid_4.set_column_homogeneous(True)
        self.vbox.add(grid_4)

        label_terminal = Gtk.Label(_('Terminal'))
        HGtk.add_class(self, label_terminal, "label_cell")
        grid_4.add(label_terminal)

        label_monitor = Gtk.Label(_('Task manager'))
        HGtk.add_class(self, label_monitor, "label_cell")
        grid_4.add(label_monitor)

        label_settings = Gtk.Label(_('Control panel'))
        HGtk.add_class(self, label_settings, "label_cell")
        grid_4.add(label_settings)
        
        self.grid_5 = Gtk.Grid()
        self.grid_5.set_column_spacing(20)
        self.grid_5.set_column_homogeneous(True)
        self.vbox.add(self.grid_5)
        
        # Regedit
        self.button_regedit = Gtk.Button.new_from_icon_name("dialog-password", Gtk.IconSize.DIALOG)
        self.button_regedit.connect("clicked", self.on_button_regedit_clicked)
        self.grid_5.add(self.button_regedit)
        
        # Uninstaller
        self.button_uninstaller = Gtk.Button.new_from_icon_name("edittrash", Gtk.IconSize.DIALOG)
        self.button_uninstaller.connect("clicked", self.on_button_uninstaller_clicked)
        self.grid_5.add(self.button_uninstaller)
        
        # Reboot
        self.button_reboot = Gtk.Button.new_from_icon_name("system-reboot", Gtk.IconSize.DIALOG)
        self.button_reboot.connect("clicked", self.on_button_reboot_clicked)
        self.grid_5.add(self.button_reboot)

        grid_6 = Gtk.Grid()
        grid_6.set_column_spacing(20)
        grid_6.set_column_homogeneous(True)
        self.vbox.add(grid_6)

        label_regedit = Gtk.Label(_('Regedit'))
        HGtk.add_class(self, label_regedit, "label_cell")
        grid_6.add(label_regedit)

        label_uninstaller = Gtk.Label(_('Uninstaller'))
        HGtk.add_class(self, label_uninstaller, "label_cell")
        grid_6.add(label_uninstaller)

        label_reboot = Gtk.Label(_('Reboot'))
        HGtk.add_class(self, label_reboot, "label_cell")
        grid_6.add(label_reboot)
        
        self.grid_7 = Gtk.Grid()
        self.grid_7.set_column_spacing(20)
        self.grid_7.set_column_homogeneous(True)
        self.vbox.add(self.grid_7)
        
        # Clone
        self.button_clone = Gtk.Button.new_from_icon_name("edit-copy", Gtk.IconSize.DIALOG)
        self.button_clone.connect("clicked", self.on_button_clone_clicked)
        self.grid_7.add(self.button_clone)
        
        # Run
        self.button_run = Gtk.Button.new_from_icon_name("application-x-msi", Gtk.IconSize.DIALOG)
        self.button_run.connect("clicked", self.on_button_run_clicked)
        self.grid_7.add(self.button_run)
        
        # Debug
        self.button_debug = Gtk.Button.new_from_icon_name("system-run", Gtk.IconSize.DIALOG)
        self.button_debug.connect("clicked", self.on_button_debug_clicked)
        self.grid_7.add(self.button_debug)

        grid_8 = Gtk.Grid()
        grid_8.set_column_spacing(20)
        grid_8.set_column_homogeneous(True)
        self.vbox.add(grid_8)

        label_clone = Gtk.Label(_('Clone'))
        HGtk.add_class(self, label_clone, "label_cell")
        grid_8.add(label_clone)

        label_run = Gtk.Label(_('Run .exe here'))
        HGtk.add_class(self, label_run, "label_cell")
        grid_8.add(label_run)

        label_debug = Gtk.Label(_('Debug'))
        HGtk.add_class(self, label_debug, "label_cell")
        grid_8.add(label_debug)

        self.grid_9 = Gtk.Grid()
        self.grid_9.set_column_spacing(20)
        self.grid_9.set_column_homogeneous(True)
        self.vbox.add(self.grid_9)
        
        # Bug
        self.button_bug = Gtk.Button.new_from_icon_name("bug", Gtk.IconSize.DIALOG)
        self.button_bug.connect("clicked", self.on_button_bug_clicked)
        self.grid_9.add(self.button_bug)
        
        # Forums
        self.button_forums = Gtk.Button.new_from_icon_name("internet-chat", Gtk.IconSize.DIALOG)
        self.button_forums.connect("clicked", self.on_button_forums_clicked)
        self.grid_9.add(self.button_forums)
        
        # AppDB
        self.button_appdb = Gtk.Button.new_from_icon_name("office-database", Gtk.IconSize.DIALOG)
        self.button_appdb.connect("clicked", self.on_button_appdb_clicked)
        self.grid_9.add(self.button_appdb)

        grid_10 = Gtk.Grid()
        grid_10.set_column_spacing(20)
        grid_10.set_column_homogeneous(True)
        self.vbox.add(grid_10)

        label_bug = Gtk.Label(_('Report bug'))
        HGtk.add_class(self, label_bug, "label_cell")
        grid_10.add(label_bug)

        label_forums = Gtk.Label(_('Forums'))
        HGtk.add_class(self, label_forums, "label_cell")
        grid_10.add(label_forums)

        label_appdb = Gtk.Label(_('Wine Database'))
        HGtk.add_class(self, label_appdb, "label_cell")
        grid_10.add(label_appdb)

    def on_button_drive_c_clicked(self, button):
        os.system('xdg-open "%s"' % self.working_dir+"/drive_c")

    def on_button_wine_cfg_clicked(self, button):
        self.wine.run_winecfg(self.working_dir)

    def on_button_winetricks_clicked(self, button):
        self.wine.run_winetricks(self.working_dir)

    def on_button_terminal_clicked(self, button):
        self.wine.run_console(self.working_dir)

    def on_button_monitor_clicked(self, button):
        self.wine.run_monitor(self.working_dir)

    def on_button_settings_clicked(self, button):
        self.wine.run_control(self.working_dir)

    def on_button_regedit_clicked(self, button):
        self.wine.run_regedit(self.working_dir)

    def on_button_uninstaller_clicked(self, button):
        self.wine.run_uninstaller(self.working_dir)

    def on_button_reboot_clicked(self, button):
        self.wine.run_wineboot(self.working_dir)

    def on_button_clone_clicked(self, button):
        self.wine.run_clone(self.working_dir)

    def on_button_run_clicked(self, button):
        file_chooser = Gtk.FileChooserDialog(
            self._('Please choose a .exe'), self.parent.parent,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        response = file_chooser.run()
        if response == Gtk.ResponseType.OK:
            self.wine.run_software(self.working_dir, file_chooser.get_filename())
            file_chooser.destroy()
        else:
            file_chooser.destroy()

    def on_button_debug_clicked(self, button):
        self.wine.run_debug(self.working_dir)

    def on_button_bug_clicked(self, button):
        # First read the documentation, then open an issue
        webbrowser.open_new_tab(cn.App.help_url)

    def on_button_forums_clicked(self, button):
        webbrowser.open_new_tab("https://forum.winehq.org/")

    def on_button_appdb_clicked(self, button):
        webbrowser.open_new_tab("https://appdb.winehq.org/")
