# main.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import gi
import gettext
import locale
import webbrowser
import subprocess

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gio, Gdk

from pathlib import Path

from .params import *
from .utils import UtilsLogger

share_dir = os.path.join(sys.prefix, 'share')
base_dir = '.'

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
    share_dir = os.path.join(base_dir, 'share')
elif sys.argv[0]:
    execdir = os.path.dirname(os.path.realpath(sys.argv[0]))
    base_dir = os.path.dirname(execdir)
    share_dir = os.path.join(base_dir, 'share')
    if not os.path.exists(share_dir):
        share_dir = base_dir

locale_dir = os.path.join(share_dir, 'locale')

if not os.path.exists(locale_dir): # development
    locale_dir = os.path.join(base_dir, 'build', 'mo')

locale.bindtextdomain("bottles", locale_dir)
locale.textdomain("bottles")
gettext.bindtextdomain("bottles", locale_dir)
gettext.textdomain("bottles")
_ = gettext.gettext

logging = UtilsLogger()

from .window import BottlesWindow

class Application(Gtk.Application):

    def __init__(self):
        super().__init__(application_id='com.usebottles.bottles',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.props.flags = Gio.ApplicationFlags.HANDLES_OPEN
        self.arg_executable = False

    def do_open(self, arg_executable, *hint):
        self.arg_executable = arg_executable[0].get_path()
        self.do_activate()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.set_actions()

    def do_activate(self):
        '''Load custom CSS'''
        data_bytes = Gio.resources_lookup_data(
            "/com/usebottles/bottles/style.css", 0)
        provider = Gtk.CssProvider()
        provider.load_from_data(data_bytes.get_data())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
                                                 provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        gtk_theme = subprocess.check_output(['gsettings',
                                             'get',
                                             'org.gnome.desktop.interface',
                                             'gtk-theme']).decode("utf-8")
        if "Yaru" in gtk_theme:
            data_bytes = Gio.resources_lookup_data(
                "/com/usebottles/bottles/yaru.css", 0)
            provider = Gtk.CssProvider()
            provider.load_from_data(data_bytes.get_data())
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
                                                     provider,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        elif "Breeze" in gtk_theme:
            data_bytes = Gio.resources_lookup_data(
                "/com/usebottles/bottles/breeze.css", 0)
            provider = Gtk.CssProvider()
            provider.load_from_data(data_bytes.get_data())
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
                                                     provider,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        '''Window'''
        win = self.props.active_window
        if not win:
            win = BottlesWindow(application=self,
                                arg_executable=self.arg_executable)

        self.win = win
        win.present()

    '''Quit application [CTRL+Q]'''

    def quit(self, action=None, param=None):
        logging.info(_("[Quit] request received."))
        self.win.destroy()

    '''Open Help URL [F1]'''
    @staticmethod
    def help(action, param):
        logging.info(_("[Help] request received."))
        webbrowser.open_new_tab("https://docs.usebottles.com")

    '''Refresh Bottles [CTRL+R]'''

    def refresh(self, action, param):
        logging.info(_("[Refresh] request received."))
        self.win.runner.update_bottles()

    '''Set application actions'''

    def set_actions(self):
        action_entries = [
            ("quit", self.quit, ("app.quit", ["<Ctrl>Q"])),
            ("help", self.help, ("app.help", ["F1"])),
            ("refresh", self.refresh, ("app.refresh", ["<Ctrl>R"]))
        ]

        for action, callback, accel in action_entries:
            simple_action = Gio.SimpleAction.new(action, None)
            simple_action.connect('activate', callback)
            self.add_action(simple_action)
            if accel is not None:
                self.set_accels_for_action(*accel)


'''Run Bottles application'''

def main(version):
    try:
        app = Application()
        return app.run(sys.argv)
    except Exception as e:
        crash = ["Error on line {}".format(
            sys.exc_info()[-1].tb_lineno), "\n", e]
        log_path = "%s/.local/share/bottles/crash.log" % Path.home()

        with open(log_path, "w") as crash_log:
            for i in crash:
                i = str(i)
                crash_log.write(i)
