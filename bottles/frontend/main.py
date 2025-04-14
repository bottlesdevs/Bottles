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
import gettext
import locale
import webbrowser
from os import path

from bottles.backend.logger import Logger
from bottles.backend.health import HealthChecker
from bottles.frontend.params import (
    APP_ID,
    APP_MAJOR_VERSION,
    APP_MINOR_VERSION,
    APP_VERSION,
)

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
gi.require_version("Xdp", "1.0")
# gi.require_version("XdpGtk4", "1.0")

# ruff: noqa: E402
from gi.repository import Gio, GLib, GObject, Adw  # type: ignore
from bottles.frontend.window import BottlesWindow
from bottles.frontend.preferences import PreferencesWindow


logging = Logger()

# region Translations
"""
This code snippet searches for and uploads translations to different
directories, depending on your production or development environment.
The function _() can be used to create and retrieve translations.
"""
share_dir = path.join(sys.prefix, "share")
base_dir = "."

if getattr(sys, "frozen", False):
    base_dir = path.dirname(sys.executable)
    share_dir = path.join(base_dir, "share")
elif sys.argv[0]:
    exec_dir = path.dirname(path.realpath(sys.argv[0]))
    base_dir = path.dirname(exec_dir)
    share_dir = path.join(base_dir, "share")

    if not path.exists(share_dir):
        share_dir = base_dir

locale_dir = path.join(share_dir, "locale")

if not path.exists(locale_dir):  # development
    locale_dir = path.join(base_dir, "build", "mo")

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
            application_id=APP_ID,
            resource_base_path="/com/usebottles/bottles",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            register_session=True,
        )
        self.__create_action("quit", self.__quit, ["<primary>q", "<primary>w"])
        self.__create_action("about", self.__show_about_dialog)
        self.__create_action("import", self.__show_importer_view, ["<primary>i"])
        self.__create_action("preferences", self.__show_preferences, ["<primary>comma"])
        self.__create_action("help", self.__help, ["F1"])
        self.__create_action("new", self.__new_bottle, ["<primary>n"])

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
            None,
        )
        self.add_main_option(
            "executable",
            ord("e"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Executable path"),
            None,
        )
        self.add_main_option(
            "lnk",
            ord("l"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("lnk path"),
            None,
        )
        self.add_main_option(
            "bottle",
            ord("b"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Bottle name"),
            None,
        )
        self.add_main_option(
            "arguments",
            ord("a"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Pass arguments"),
            None,
        )
        self.add_main_option(
            GLib.OPTION_REMAINING,
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING_ARRAY,
            "URI",
            None,
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
            print(APP_VERSION)
            quit()

        if commands.contains("bottle"):
            self.arg_bottle = commands.lookup_value("bottle").get_string()

        if not self.arg_exe:
            """
            If no executable is specified, look if it was passed without
            the --executable argument.
            """
            for a in sys.argv:
                if a.endswith((".exe", ".msi", ".bat", ".lnk")):
                    self.arg_exe = a
                    logging.info(
                        _("Launching with executable: {0}").format(a),
                    )

        uri = commands.lookup_value(GLib.OPTION_REMAINING)
        logging.info(
            _("Launching with URI: {0}").format(uri),
        )
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

        if uri.startswith("bottles:run/"):
            if len(uri.split("/")) != 3:
                logging.error(_("Invalid URI (syntax: bottles:run/<bottle>/<program>)"))
                return False

            uri = uri.replace("bottles:run/", "")
            bottle, program = uri.split("/")

            import subprocess

            subprocess.Popen(["bottles-cli", "run", "-b", bottle, "-p", program])
            return 0

        try:
            from bottles.frontend.bottle_picker_dialog import BottlePickerDialog

            dialog = BottlePickerDialog(application=self, arg_exe=uri)
            dialog.present()
            return 0
        except Exception as e:
            logging.error(
                _("Error while processing URI: {0}").format(e),
            )
            return False

    def do_startup(self):
        """
        This function is called when the application is started.
        Here we register the application actions (shortcuts).
        See: __register_actions()
        """
        Adw.Application.do_startup(self)

    def do_activate(self):
        """
        This function is called when the application is activated.
        """

        logging.info(
            _("[Activate] request received."),
        )

        # create the main window
        Adw.Application.do_activate(self)
        win = self.props.active_window
        if not win:
            win = BottlesWindow(application=self, arg_bottle=self.arg_bottle)
        self.win = win

        win.present()

    def __quit(self, *args):
        """
        This function close the application.
        It is used by the [Ctrl+Q] shortcut.
        """
        logging.info(
            _("[Quit] request received."),
        )
        self.win.on_close_request()
        quit()

    @staticmethod
    def __help(action=None, param=None):
        """
        This function open the documentation in the user's default browser.
        It is used by the [F1] shortcut.
        """
        logging.info(
            _("[Help] request received."),
        )
        webbrowser.open_new_tab("https://docs.usebottles.com")

    def __refresh(self, action=None, param=None):
        """
        This function refresh the user bottle list.
        It is used by the [Ctrl+R] shortcut.
        """
        logging.info(
            _("[Refresh] request received."),
        )
        self.win.manager.update_bottles()

    def __show_preferences(self, *args):
        preferences_window = PreferencesWindow(self.win)
        preferences_window.present()

    def __new_bottle(self, *args):
        self.win.show_add_view()

    def __show_importer_view(self, widget=False, *args):
        self.win.main_leaf.push(self.win.page_importer)

    def __show_about_dialog(self, *_args):
        developers = [
            "Mirko Brombin https://github.com/mirkobrombin",
            "hthre7 https://github.com/hthre7",
            "Kekun https://github.com/Kekun",
            "Sonny Piers https://github.com/sonnyp",
            "BrainBlasted https://github.com/BrainBlasted",
            "Francesco Masala <mail@francescomasala.me>",
            "Hari Rana (TheEvilSkeleton) https://theevilskeleton.gitlab.io",
            "axtlos https://axtloss.github.io",
            "Oro https://github.com/orowith2os",
            "gregorni https://gitlab.com/gregorni",
        ]

        artists = [
            "Marco Montini https://github.com/marckniack",
            "Noëlle https://github.com/jannuary",
            "Alvar Lagerlöf https://github.com/alvarlagerlof",
            "Ezekiel Smith https://github.com/ZekeSmith",
        ]

        about_dialog = Adw.AboutDialog.new_from_appdata(
            "/com/usebottles/bottles/appdata",
            f"{APP_MAJOR_VERSION}.{APP_MINOR_VERSION}",
        )
        about_dialog.set_developers(developers)
        about_dialog.set_translator_credits(_("translator_credits"))
        about_dialog.set_artists(artists)
        about_dialog.set_debug_info(HealthChecker().get_results(plain=True))
        about_dialog.add_link(_("Donate"), "https://usebottles.com/funding")
        about_dialog.set_copyright(
            _("Copyright © 2017 {developer_name}").format(
                developer_name=about_dialog.get_developer_name()
            )
        )
        about_dialog.add_acknowledgement_section(
            _("Third-Party Libraries and Special Thanks"),
            [
                "DXVK https://github.com/doitsujin/dxvk",
                "VKD3D https://github.com/HansKristian-Work/vkd3d-proton",
                "DXVK-NVAPI https://github.com/jp7677/dxvk-nvapi",
                "LatencyFleX https://github.com/ishitatsuyuki/LatencyFleX",
                "MangoHud https://github.com/flightlessmango/MangoHud",
                "AMD FidelityFX™ Super Resolution https://www.amd.com/en/technologies/fidelityfx-super-resolution",
                "vkBasalt https://github.com/DadSchoorse/vkBasalt",
                "vkbasalt-cli https://gitlab.com/TheEvilSkeleton/vkbasalt-cli",
                "GameMode https://github.com/FeralInteractive/gamemode",
                "Gamescope https://github.com/Plagman/gamescope",
                "OBS Vulkan/OpenGL capture https://github.com/nowrep/obs-vkcapture",
                "Wine-TKG https://github.com/Frogging-Family/wine-tkg-git",
                "Proton https://github.com/ValveSoftware/proton",
                "Wine-GE https://github.com/GloriousEggroll/wine-ge-custom",
                "Wine https://www.winehq.org",
                "orjson https://github.com/ijl/orjson",
                "libadwaita https://gitlab.gnome.org/GNOME/libadwaita",
                "icoextract https://github.com/jlu5/icoextract",
                "vmtouch https://github.com/hoytech/vmtouch",
                "FVS https://github.com/mirkobrombin/FVS",
                "pathvalidate https://github.com/thombashi/pathvalidate",
            ],
        )
        about_dialog.add_acknowledgement_section(
            _("Sponsored and Funded by"),
            [
                "JetBrains https://www.jetbrains.com/?from=bottles",
                "GitBook https://www.gitbook.com/?ref=bottles",
                "Linode https://www.linode.com/?from=bottles",
                "Appwrite https://appwrite.io/?from=bottles",
                "Community ❤️ https://usebottles.com/funding",
            ],
        )
        about_dialog.present(self.win)

    def __create_action(self, name, callback, shortcuts=None, param=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
            param: an optional list of parameters for the action
        """
        action = Gio.SimpleAction.new(name, param)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


GObject.threads_init()


def main(version):
    app = Bottles()
    return app.run(sys.argv)
