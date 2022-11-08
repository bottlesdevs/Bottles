# list.py
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
from datetime import datetime
from gettext import gettext as _
from gi.repository import Gtk, GLib, Adw

from bottles.frontend.windows.filechooser import FileChooser  # pyright: reportMissingImports=false

from bottles.frontend.utils.threading import RunAsync
from bottles.backend.runner import Runner
from bottles.backend.wine.executor import WineExecutor


@Gtk.Template(resource_path='/com/usebottles/bottles/list-entry.ui')
class BottleViewEntry(Adw.ActionRow):
    __gtype_name__ = 'BottleViewEntry'

    Adw.init()

    # region Widgets
    btn_run = Gtk.Template.Child()
    btn_repair = Gtk.Template.Child()
    btn_run_executable = Gtk.Template.Child()
    details_image = Gtk.Template.Child()
    label_env = Gtk.Template.Child()
    label_state = Gtk.Template.Child()
    icon_damaged = Gtk.Template.Child()
    grid_versioning = Gtk.Template.Child()
    spinner = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config[1]
        self.label_env_context = self.label_env.get_style_context()

        '''Format update date'''
        update_date = _("N/A")
        if self.config.get("Update_Date"):
            try:
                update_date = datetime.strptime(self.config.get("Update_Date"), "%Y-%m-%d %H:%M:%S.%f")
                update_date = update_date.strftime("%d %B, %Y %H:%M:%S")
            except ValueError:
                update_date = _("N/A")

        '''Check runner type by name'''
        if self.config.get("Runner").startswith("lutris"):
            self.runner_type = "wine"
        else:
            self.runner_type = "proton"

        # connect signals
        activate_handler = self.connect('activated', self.show_details)
        self.btn_run.connect("clicked", self.run_executable)
        self.btn_repair.connect("clicked", self.repair)
        self.btn_run_executable.connect("clicked", self.run_executable)

        # populate widgets
        self.grid_versioning.set_visible(self.config.get("Versioning"))
        self.label_state.set_text(str(self.config.get("State")))
        self.set_title(self.config.get("Name"))
        if self.window.settings.get_boolean("update-date"):
            self.set_subtitle(update_date)
        self.label_env.set_text(_(self.config.get("Environment")))
        self.label_env_context.add_class(
            "tag-%s" % self.config.get("Environment").lower())

        '''If config is broken'''
        if self.config.get("Broken"):
            for w in [self.btn_repair, self.icon_damaged]:
                w.set_visible(True)
                w.set_sensitive(True)

            self.btn_run.set_sensitive(False)
            self.handler_block_by_func(self.show_details)

    '''Repair bottle'''

    def repair(self, widget):
        self.disable()
        RunAsync(
            task_func=self.manager.repair_bottle,
            config=self.config
        )

    '''Display file dialog for executable'''

    def run_executable(self, *_args):
        def set_path(_dialog, response, _file_dialog):
            if response == -3:
                _file = _file_dialog.get_file()
                _executor = WineExecutor(self.config, exec_path=_file.get_path())
                RunAsync(_executor.run)

        FileChooser(
            parent=self.window,
            title=_("Choose a Windows executable file"),
            action=Gtk.FileChooserAction.OPEN,
            buttons=(_("Cancel"), _("Run")),
            callback=set_path
        )

    def show_details(self, widget=None, config=None):
        if config is None:
            config = self.config
        self.window.page_details.view_preferences.update_combo_components()
        self.window.show_details_view(config=config)

    def disable(self):
        self.window.go_back()
        self.set_visible(False)


@Gtk.Template(resource_path='/com/usebottles/bottles/list.ui')
class BottleView(Adw.Bin):
    __gtype_name__ = 'BottleView'
    __bottles = {}

    # region Widgets
    list_bottles = Gtk.Template.Child()
    list_steam = Gtk.Template.Child()
    group_bottles = Gtk.Template.Child()
    group_steam = Gtk.Template.Child()
    pref_page = Gtk.Template.Child()
    bottle_status = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    no_bottles_found = Gtk.Template.Child()

    # endregion

    def __init__(self, window, arg_bottle=None, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.arg_bottle = arg_bottle

        # connect signals
        self.btn_create.connect("clicked", self.window.show_add_view)
        self.entry_search.connect('changed', self.__search_bottles)

        self.update_bottles()

    def __search_bottles(self, widget, event=None, data=None):
        """
        This function search in the list of bottles the
        text written in the search entry.
        """
        terms = widget.get_text()
        self.list_bottles.set_filter_func(
            self.__filter_bottles,
            terms
        )

    @staticmethod
    def __filter_bottles(row, terms=None):
        text = row.get_title().lower()
        if terms.lower() in text:
            return True
        return False

    def idle_update_bottles(self, show=False):
        self.__bottles = {}
        while self.list_bottles.get_first_child():
            self.list_bottles.remove(self.list_bottles.get_first_child())

        while self.list_steam.get_first_child():
            self.list_steam.remove(self.list_steam.get_first_child())

        local_bottles = self.window.manager.local_bottles
        bottles = local_bottles.items()

        if len(bottles) == 0:
            self.pref_page.set_visible(False)
            self.bottle_status.set_visible(True)
        else:
            self.pref_page.set_visible(True)
            self.bottle_status.set_visible(False)

        for bottle in bottles:
            _entry = BottleViewEntry(self.window, bottle)
            self.__bottles[bottle[1]["Path"]] = _entry

            if bottle[1].get("Environment") != "Steam":
                self.list_bottles.append(_entry)
            else:
                self.list_steam.append(_entry)

            if self.list_steam.get_first_child() is None:
                self.group_steam.set_visible(False)
                self.group_bottles.set_title("")
            else:
                self.group_steam.set_visible(True)
                self.group_bottles.set_title(_("Your Bottles"))

        if (self.arg_bottle is not None and self.arg_bottle in local_bottles.keys()) \
                or (show is not None and show in local_bottles.keys()):
            if self.arg_bottle:
                _config = local_bottles[self.arg_bottle]
            if show:
                _config = local_bottles[show]
            self.window.page_details.view_preferences.update_combo_components()
            self.window.show_details_view(config=_config)
            self.arg_bottle = None

    def update_bottles(self, show=False):
        GLib.idle_add(self.idle_update_bottles, show)

    def disable_bottle(self, config):
        self.__bottles[config["Path"]].disable()
