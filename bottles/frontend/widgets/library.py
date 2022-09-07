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
#

import logging
import os
import math
from PIL import Image
from datetime import datetime
from gettext import gettext as _
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Adw

from bottles.frontend.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.backend.managers.library import LibraryManager
from bottles.backend.managers.thumbnail import ThumbnailManager
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
    btn_menu = Gtk.Template.Child()

    # endregion

    def __init__(self, library, uuid, entry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.library = library
        self.manager = library.window.manager
        self.uuid = uuid
        self.entry = entry
        self.config = self.__get_config()
        if self.config is None:
            self.__remove_entry()
            return

        self.program = self.__get_program()
        self.set_size_request(240, 420)

        if len(entry['name']) >= 15:
            name = entry['name'][:13] + "…"
        else:
            name = entry['name']

        self.label_name.set_text(name)
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
            self.img_icon.set_visible(True)

        if entry.get('thumbnail'):
            path = ThumbnailManager.get_path(self.config, entry['thumbnail'])
            #texture = Gdk.Texture.new_from_filename(path)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 240, 360)
            self.img_cover.set_pixbuf(pixbuf)
            #self.img_cover.set_paintable(texture)
            self.img_cover.set_visible(True)
            self.label_no_cover.set_visible(False)
            self.__calculate_button_color(path=path)

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
                w.set_visible(False)
                w.set_sensitive(False)
            self.btn_launch_steam.set_visible(True)
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

    def __remove_entry(self, *args):
        self.library.remove_entry(self.uuid)

    def __calculate_button_color(self, path):
        image = Image.open(path)
        image = image.crop((0, 0, 47, 58))
        image.thumbnail((150, 150))
        palette = image.convert('P', palette=Image.ADAPTIVE, colors=1).getpalette()
        rgb = (255-palette[0], 255-palette[1], 255-palette[2])
        button_color = math.floor(0.299*rgb[0])+math.floor(0.587*rgb[1])+math.floor(0.144*rgb[2])
        self.library.add_css_entry(entry=self, color=button_color)

    def run_executable(self, widget, with_terminal=False):
        RunAsync(
            WineExecutor.run_program, 
            callback=self.__reset_buttons, 
            config=self.config, 
            program=self.program
        )
        self.__reset_buttons()

    def run_steam(self, widget):
        self.manager.steam_manager.launch_app(self.config["CompatData"])

    def stop_process(self, widget):
        winedbg = WineDbg(self.config)
        winedbg.kill_process(name=self.program["executable"])
        self.__reset_buttons(True)
