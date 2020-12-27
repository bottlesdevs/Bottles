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

import os, sys, gi, gettext, locale

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gio, Gdk

from pathlib import Path

from .params import *

'''
Custom locale path if AppImage
'''
try:
    LOCALE_PATH = "%s/usr/share/locale/" % os.environ['APPDIR']
except:
    LOCALE_PATH = "/usr/local/share/locale/"

locale.bindtextdomain(APP_NAME_LOWER, LOCALE_PATH)
locale.textdomain(APP_NAME_LOWER)
gettext.bindtextdomain(APP_NAME_LOWER, LOCALE_PATH)
gettext.textdomain(APP_NAME_LOWER)
_ = gettext.gettext

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

    def do_activate(self):

        '''
        Load custom css
        '''
        bytes = Gio.resources_lookup_data("/com/usebottles/bottles/style.css", 0)
        provider = Gtk.CssProvider()
        provider.load_from_data(bytes.get_data())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
                                                 provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        '''
        Window
        '''
        win = self.props.active_window
        if not win:
            win = BottlesWindow(application=self,
                                arg_executable=self.arg_executable)

        win.present()

def main(version):
    try:
        app = Application()
        return app.run(sys.argv)
    except Exception as e:
        crash=["Error on line {}".format(sys.exc_info()[-1].tb_lineno),"\n",e]
        log_path = "%s/.local/share/bottles/crash.log" % Path.home()

        with open(log_path,"w") as crash_log:
            for i in crash:
                i = str(i)
                crash_log.write(i)
