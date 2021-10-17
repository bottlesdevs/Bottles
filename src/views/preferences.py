# preferences.py
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

from gettext import gettext as _
from gi.repository import Gtk, Handy

from ..widgets.component import ComponentEntry


@Gtk.Template(resource_path='/com/usebottles/bottles/preferences.ui')
class PreferencesWindow(Handy.PreferencesWindow):
    __gtype_name__ = 'PreferencesWindow'

    # region Widgets
    switch_dark = Gtk.Template.Child()
    switch_notifications = Gtk.Template.Child()
    switch_temp = Gtk.Template.Child()
    switch_release_candidate = Gtk.Template.Child()
    switch_versioning = Gtk.Template.Child()
    switch_installers = Gtk.Template.Child()
    switch_auto_close = Gtk.Template.Child()
    switch_update_date = Gtk.Template.Child()
    list_runners = Gtk.Template.Child()
    list_dxvk = Gtk.Template.Child()
    list_vkd3d = Gtk.Template.Child()
    list_nvapi = Gtk.Template.Child()
    actionrow_prerelease = Gtk.Template.Child()
    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.settings = window.settings
        self.default_settings = window.default_settings
        self.manager = window.manager

        # set widget defaults
        self.switch_dark.set_active(
            self.settings.get_boolean("dark-theme")
        )
        self.switch_notifications.set_active(
            self.settings.get_boolean("notifications")
        )
        self.switch_temp.set_active(
            self.settings.get_boolean("temp")
        )
        self.switch_release_candidate.set_active(
            self.settings.get_boolean("release-candidate")
        )
        self.switch_versioning.set_active(
            self.settings.get_boolean("experiments-versioning")
        )
        self.switch_installers.set_active(
            self.settings.get_boolean("experiments-installers")
        )
        self.switch_auto_close.set_active(
            self.settings.get_boolean("auto-close-bottles")
        )
        self.switch_update_date.set_active(
            self.settings.get_boolean("update-date")
        )
        self.populate_runners_list()
        self.populate_dxvk_list()
        self.populate_vkd3d_list()
        self.populate_nvapi_list()

        # connect signals
        self.switch_dark.connect('state-set', self.__toggle_dark)
        self.switch_notifications.connect('state-set', self.__toggle_notify)
        self.switch_temp.connect('state-set', self.__toggle_temp)
        self.switch_release_candidate.connect('state-set', self.__toggle_rc)
        self.switch_versioning.connect('state-set', self.__toggle_versioning)
        self.switch_installers.connect('state-set', self.__toggle_installers)
        self.switch_auto_close.connect('state-set', self.__toggle_autoclose)
        self.switch_update_date.connect('state-set', self.__toggle_update_date)

    def __toggle_dark(self, widget, state):
        self.settings.set_boolean("dark-theme", state)
        self.default_settings.set_property(
            "gtk-application-prefer-dark-theme",
            state
        )

    def __toggle_update_date(self, widget, state):
        self.settings.set_boolean("update-date", state)
        self.window.page_list.update_bottles()

    def __toggle_notify(self, widget, state):
        self.settings.set_boolean("notifications", state)

    def __toggle_rc(self, widget, state):
        self.settings.set_boolean("release-candidate", state)
        self.populate_runners_list()

    def __toggle_temp(self, widget, state):
        self.settings.set_boolean("temp", state)

    def __toggle_versioning(self, widget, state):
        self.settings.set_boolean("experiments-versioning", state)
        self.window.page_details.build_pages()

    def __toggle_installers(self, widget, state):
        self.settings.set_boolean("experiments-installers", state)
        self.window.page_details.build_pages()

    def __toggle_autoclose(self, widget, state):
        self.settings.set_boolean("auto-close-bottles", state)

    def populate_dxvk_list(self):
        for dxvk in self.manager.supported_dxvk.items():
            self.list_dxvk.add(ComponentEntry(self.window, dxvk, "dxvk"))

    def populate_vkd3d_list(self):
        for vkd3d in self.manager.supported_vkd3d.items():
            self.list_vkd3d.add(ComponentEntry(self.window, vkd3d, "vkd3d"))

    def populate_nvapi_list(self):
        for nvapi in self.manager.supported_nvapi.items():
            self.list_nvapi.add(ComponentEntry(self.window, nvapi, "nvapi"))

    def populate_runners_list(self):
        for w in self.list_runners:
            if w != self.actionrow_prerelease:
                w.destroy()

        for runner in self.manager.supported_wine_runners.items():
            if (not self.window.settings.get_boolean("release-candidate")
                    and runner[1]["Channel"] in ["rc", "unstable"]):
                continue
            self.list_runners.add(ComponentEntry(self.window, runner, "runner"))

        for runner in self.manager.supported_proton_runners.items():
            if (not self.window.settings.get_boolean("release-candidate")
                    and runner[1]["Channel"] in ["rc", "unstable"]):
                continue
            self.list_runners.add(ComponentEntry(
                self.window, 
                runner, 
                "runner:proton"
                )
            )
