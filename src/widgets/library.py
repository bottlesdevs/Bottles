# library.py
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

import logging
import os
from datetime import datetime
from gettext import gettext as _
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Adw

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.backend.managers.library import LibraryManager
from bottles.backend.runner import Runner
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.executor import WineExecutor


@Gtk.Template(resource_path='/com/usebottles/bottles/library-entry.ui')
class LibraryEntry(Gtk.Box):
    __gtype_name__ = 'LibraryEntry'

    # region Widgets
    btn_run = Gtk.Template.Child()
    btn_stop = Gtk.Template.Child()
    btn_launch_steam = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    label_name = Gtk.Template.Child()
    label_bottle = Gtk.Template.Child()
    label_no_cover = Gtk.Template.Child()
    img_cover = Gtk.Template.Child()
    img_icon = Gtk.Template.Child()

    # endregion

    def __init__(self, library, uuid, entry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.library = library
        self.manager = library.window.manager
        self.uuid = uuid
        self.entry = entry
        self.config = self.__get_config()
        self.program = self.__get_program()

        self.label_name.set_text(entry['name'])
        self.label_bottle.set_text(entry['bottle']['name'])

        if entry.get('icon'):
            use_default = False
            if os.path.exists(entry['icon']):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(entry['icon'], 24, 24)
                    self.img_icon.set_from_pixbuf(pixbuf)
                except GLib.GError:
                    use_default = True
            if entry['icon'] == "com.usebottles.bottles-program" or use_default:
                self.img_icon.set_from_icon_name("com.usebottles.bottles-program")
            self.img_icon.set_pixel_size(24)
            self.img_icon..show()

        # TODO:
        # is has cover:
            # set img_cover visible
        # else
            # set label_no_cover visible
        self.label_no_cover..show()

        self.btn_run.connect("clicked", self.run_executable)
        self.btn_launch_steam.connect("clicked", self.run_steam)
        self.btn_stop.connect("clicked", self.stop_process)
        self.btn_remove.connect("clicked", self.__remove_entry)

        '''
        if is_steam:
            self.set_subtitle(_("This is a Steam application"))
            for w in [
                self.btn_run,
                self.btn_stop,
                self.btn_menu,
                self.sep
            ]:
                w..hide()
                w.set_sensitive(False)
            self.btn_launch_steam..show()
            self.btn_launch_steam.set_sensitive(True)
        '''

    def __get_config(self):
        bottles = self.manager.local_bottles
        if self.entry['bottle']['name'] in bottles:
            return bottles[self.entry['bottle']['name']]
        parent = self.get_parent()
        if parent:
            parent.remove(self)  # TODO: Remove from list

    def __get_program(self):
        programs = self.manager.get_programs(self.config)
        programs = [p for p in programs if p["id"] == self.entry["id"] or p["name"] == self.entry["name"]]
        if len(programs) == 0:
            return None  # TODO: remove entry from library
        return programs[0]

    def __reset_buttons(self, result=False, error=False):
        status = False
        if result:
            status = result
            if not isinstance(result, bool):
                status = result.status
        self.btn_run.set_visible(status)
        self.btn_stop.set_visible(not status)

    def __is_alive(self):
        winedbg = WineDbg(self.config)

        def set_watcher(result=False, error=False):
            nonlocal winedbg
            self.__reset_buttons()

            RunAsync(
                winedbg.wait_for_process,
                callback=self.__reset_buttons,
                name=self.program["executable"],
                timeout=5
            )

        RunAsync(
            winedbg.is_process_alive,
            callback=set_watcher,
            name=self.program["executable"]
        )

    def __remove_entry(self, widget):
        self.library.remove_entry(self.uuid)

    def run_executable(self, widget, with_terminal=False):
        executor = WineExecutor(
            self.config,
            exec_path=self.program["path"],
            args=self.program["arguments"],
            cwd=self.program["folder"],
            post_script=self.program.get("script", None),
            terminal=with_terminal
        )
        RunAsync(executor.run, callback=self.__reset_buttons)

        self.__reset_buttons()

    def run_steam(self, widget):
        self.manager.steam_manager.launch_app(self.config["CompatData"])

    def stop_process(self, widget):
        winedbg = WineDbg(self.config)
        winedbg.kill_process(name=self.program["executable"])
        self.__reset_buttons(True)
