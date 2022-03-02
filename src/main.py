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

import sys
import gi
import gettext
import locale
import webbrowser
import subprocess
from os import path

gi.require_version('Gtk', '3.0')
gi.require_version('Handy', '1')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, Gio, Gdk, GLib, GObject, Handy

from bottles.params import *
from bottles.backend.logger import Logger
from bottles.window import MainWindow

logging = Logger()

# region Translations
'''
This code snippet searches for and uploads translations to different 
directories, depending on your production or development environment. 
The function _() can be used to create and retrieve translations.
'''
share_dir = path.join(sys.prefix, 'share')
base_dir = '.'

if getattr(sys, 'frozen', False):
    base_dir = path.dirname(sys.executable)
    share_dir = path.join(base_dir, 'share')
elif sys.argv[0]:
    exec_dir = path.dirname(path.realpath(sys.argv[0]))
    base_dir = path.dirname(exec_dir)
    share_dir = path.join(base_dir, 'share')

    if not path.exists(share_dir):
        share_dir = base_dir

locale_dir = path.join(share_dir, 'locale')

if not path.exists(locale_dir):  # development
    locale_dir = path.join(base_dir, 'build', 'mo')

locale.bindtextdomain("bottles", locale_dir)
locale.textdomain("bottles")
gettext.bindtextdomain("bottles", locale_dir)
gettext.textdomain("bottles")
_ = gettext.gettext


# endregion


class Bottles(Gtk.Application):
    arg_exe = False
    arg_bottle = False
    arg_passed = False

    def __init__(self):
        super().__init__(
            application_id='com.usebottles.bottles',
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        self.__register_arguments()

    def __register_arguments(self):
        '''
        This function registers the command line arguments.
            --version, -v: Prints the version of the application.
            --executable, -e: The path of the executable to be launched.
            --lnk, -l: The path of the shortcut to be launched.
            --bottle, -b: The name of the bottle to be used.
            --arguments, -a: The arguments to be passed to the executable.
            --help, -h: Prints the help.
        '''
        self.add_main_option(
            "version",
            ord("v"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Show version"),
            None
        )
        self.add_main_option(
            "executable",
            ord("e"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Executable path"),
            None
        )
        self.add_main_option(
            "lnk",
            ord("l"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("lnk path"),
            None
        )
        self.add_main_option(
            "bottle",
            ord("b"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Bottle name"),
            None
        )
        self.add_main_option(
            "arguments",
            ord("a"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Pass arguments"),
            None
        )

    def do_command_line(self, command):
        '''
        This function is called when the application is launched from the
        command line. It parses the command line arguments and calls the
        corresponding functions.
        See: __register_arguments()
        '''
        commands = command.get_options_dict()

        if commands.contains("executable"):
            self.arg_exe = commands.lookup_value("executable").get_string()

        if commands.contains("version"):
            print(VERSION)
            quit()

        if commands.contains("lnk"):
            self.arg_exe = commands.lookup_value("lnk").get_string()

        if commands.contains("bottle"):
            self.arg_bottle = commands.lookup_value("bottle").get_string()

        if commands.contains("arguments"):
            self.arg_passed = commands.lookup_value("arguments").get_string()

        if not self.arg_exe:
            '''
            If no executable is specified, look if it was passed without
            the --executable argument.
            '''
            for a in sys.argv:
                if a.endswith(('.exe', '.msi', '.bat', '.lnk')):
                    self.arg_exe = a

        self.do_activate()

        return 0

    def do_startup(self):
        '''
        This function is called when the application is started.
        Here we register the application actions (shortcuts).
        See: __register_actions()
        '''
        Gtk.Application.do_startup(self)
        self.__register_actions()

        # Opt-in to follow dark mode user preference.
        # TODO Remove after porting to libadwaita.
        manager = Handy.StyleManager.get_default()
        manager.set_color_scheme(Handy.ColorScheme.PREFER_LIGHT)

    def do_activate(self):
        '''
        This function is called when the application is activated.
        We use this to load the custom css providers and spawn the 
        main window.
        '''

        # region css_provider
        # check the user theme and load the corresponding css
        user_theme = subprocess.check_output([
            'gsettings',
            'get',
            'org.gnome.desktop.interface',
            'gtk-theme'
        ]).decode("utf-8")
        css_res = False
        if "Yaru" in user_theme:
            css_res = Gio.resources_lookup_data(
                path="/com/usebottles/bottles/yaru.css",
                lookup_flags=0
            )
        # elif "Breeze" in user_theme:
        #     css_res = Gio.resources_lookup_data(
        #         path="/com/usebottles/bottles/breeze.css",
        #         lookup_flags=0
        #     )
        elif "io.elementary.stylesheet" in user_theme:
            css_res = Gio.resources_lookup_data(
                path="/com/usebottles/bottles/elementary.css",
                lookup_flags=0
            )

        css_def = Gio.resources_lookup_data(
            path="/com/usebottles/bottles/style.css",
            lookup_flags=0
        )

        provider = Gtk.CssProvider()
        if css_res:
            provider.load_from_data(css_def.get_data() + css_res.get_data())
        else:
            provider.load_from_data(css_def.get_data())
        Gtk.StyleContext.add_provider_for_screen(
            screen=Gdk.Screen.get_default(),
            provider=provider,
            priority=Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        # endregion

        # create the main window
        win = self.props.active_window
        if not win:
            win = MainWindow(
                application=self,
                arg_exe=self.arg_exe,
                arg_bottle=self.arg_bottle,
                arg_passed=self.arg_passed
            )
        self.win = win
        win.present()

    @staticmethod
    def __quit(action=None, param=None):
        '''
        This function close the application.
        It is used by the [Ctrl+Q] shortcut.
        '''
        logging.info(_("[Quit] request received."), )
        quit()

    @staticmethod
    def __help(action=None, param=None):
        '''
        This function open the documentation in the user's default browser.
        It is used by the [F1] shortcut.
        '''
        logging.info(_("[Help] request received."), )
        webbrowser.open_new_tab("https://docs.usebottles.com")

    def __refresh(self, action=None, param=None):
        '''
        This function refresh the user bottle list.
        It is used by the [Ctrl+R] shortcut.
        '''
        logging.info(_("[Refresh] request received."), )
        self.win.manager.update_bottles()

    def __register_actions(self):
        '''
        This function registers the application actions.
        The actions are the application shortcuts (accellerators).
        '''
        action_entries = [
            ("quit", self.__quit, ("app.quit", ["<Ctrl>Q"])),
            ("help", self.__help, ("app.help", ["F1"])),
            ("refresh", self.__refresh, ("app.refresh", ["<Ctrl>R"]))
        ]

        for action, callback, accel in action_entries:
            simple_action = Gio.SimpleAction.new(action, None)
            simple_action.connect('activate', callback)
            self.add_action(simple_action)
            if accel is not None:
                self.set_accels_for_action(*accel)


GObject.threads_init()


def main(version):
    app = Bottles()
    return app.run(sys.argv)
