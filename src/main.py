# main.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import gi
import os
import gettext
import locale
import webbrowser
import subprocess
from os import path

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GtkSource', '5')
#gi.require_version("Xdp", "1.0")
#gi.require_version("XdpGtk4", "1.0")

from gi.repository import Gtk, Gio, Gdk, GLib, GObject, Adw

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


class Bottles(Adw.Application):
    arg_exe = None
    arg_bottle = None
    dark_provider = None

    def __init__(self):
        super().__init__(
            application_id='com.usebottles.bottles',
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            register_session=True
        )
        self.win = None
        self.__register_arguments()

    def __register_arguments(self):
        """
        This function registers the command line arguments.
            --version, -v: Prints the version of the application.
            --executable, -e: The path of the executable to be launched.
            --lnk, -l: The path of the shortcut to be launched.
            --bottle, -b: The name of the bottle to be used.
            --arguments, -a: The arguments to be passed to the executable.
            --help, -h: Prints the help.
        """
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
        self.add_main_option(
            GLib.OPTION_REMAINING,
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING_ARRAY,
            "URI",
            None
        )

    def do_command_line(self, command):
        """
        This function is called when the application is launched from the
        command line. It parses the command line arguments and calls the
        corresponding functions.
        See: __register_arguments()
        """
        commands = command.get_options_dict()

        if commands.contains("executable"):
            self.arg_exe = commands.lookup_value("executable").get_string()

        if commands.contains("version"):
            print(VERSION)
            quit()

        if commands.contains("bottle"):
            self.arg_bottle = commands.lookup_value("bottle").get_string()

        if not self.arg_exe:
            '''
            If no executable is specified, look if it was passed without
            the --executable argument.
            '''
            for a in sys.argv:
                if a.endswith(('.exe', '.msi', '.bat', '.lnk')):
                    self.arg_exe = a

        uri = commands.lookup_value(GLib.OPTION_REMAINING)
        if uri:
            return self.__process_uri(uri)

        self.do_activate()
        return 0

    def __process_uri(self, uri):
        """
        This function processes the URI passed to the application.
        e.g. xdg-open bottles:run/<bottle>/<program>
        """
        uri = uri[0]
        if os.path.exists(uri):
            from bottles.dialogs.bottlepicker import BottlePickerDialog
            dialog = BottlePickerDialog(application=self, arg_exe=uri)
            dialog.present()
            return 0

        _wrong_uri_error = _("Invalid URI (syntax: bottles:run/<bottle>/<program>)")
        if not len(uri) > 0 or not uri.startswith('bottles:run/') or len(uri.split('/')) != 3:
            print(_wrong_uri_error)
            return False

        uri = uri.replace('bottles:run/', '')
        bottle, program = uri.split('/')

        import subprocess
        subprocess.Popen(['bottles-cli', 'run', '-b', bottle, '-p', program])

    def do_startup(self):
        """
        This function is called when the application is started.
        Here we register the application actions (shortcuts).
        See: __register_actions()
        """
        Adw.Application.do_startup(self)
        self.__register_actions()

    def do_activate(self):
        """
        This function is called when the application is activated.
        """

        # create the main window
        win = self.props.active_window
        if not win:
            win = MainWindow(
                application=self,
                arg_bottle=self.arg_bottle
            )
        self.win = win
        win.present()

    @staticmethod
    def __quit(action=None, param=None):
        """
        This function close the application.
        It is used by the [Ctrl+Q] shortcut.
        """
        logging.info(_("[Quit] request received."), )
        quit()

    @staticmethod
    def __help(action=None, param=None):
        """
        This function open the documentation in the user's default browser.
        It is used by the [F1] shortcut.
        """
        logging.info(_("[Help] request received."), )
        webbrowser.open_new_tab("https://docs.usebottles.com")

    def __refresh(self, action=None, param=None):
        """
        This function refresh the user bottle list.
        It is used by the [Ctrl+R] shortcut.
        """
        logging.info(_("[Refresh] request received."), )
        self.win.manager.update_bottles()

    def __register_actions(self):
        """
        This function registers the application actions.
        The actions are the application shortcuts (accellerators).
        """
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
