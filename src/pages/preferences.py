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

from gi.repository import Gtk, GLib, Handy

@Gtk.Template(resource_path='/com/usebottles/bottles/preferences.ui')
class BottlesPreferences(Handy.PreferencesWindow):
    __gtype_name__ = 'BottlesPreferences'

    '''Get widgets from template'''
    switch_dark = Gtk.Template.Child()
    switch_notifications = Gtk.Template.Child()
    switch_temp = Gtk.Template.Child()
    switch_release_candidate = Gtk.Template.Child()
    switch_versioning = Gtk.Template.Child()
    switch_installers = Gtk.Template.Child()
    list_dxvk = Gtk.Template.Child()
    list_runners = Gtk.Template.Child()
    actionrow_prerelease = Gtk.Template.Child()

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        '''Init template'''
        self.init_template()

        '''Common variables'''
        self.window = window
        self.settings = window.settings
        self.default_settings = window.default_settings
        self.runner = window.runner

        '''Set widgets status from user settings'''
        self.switch_dark.set_active(self.settings.get_boolean("dark-theme"))
        self.switch_notifications.set_active(self.settings.get_boolean("notifications"))
        self.switch_temp.set_active(self.settings.get_boolean("temp"))
        self.switch_release_candidate.set_active(self.settings.get_boolean("release-candidate"))
        self.switch_versioning.set_active(self.settings.get_boolean("experiments-versioning"))
        self.switch_installers.set_active(self.settings.get_boolean("experiments-installers"))

        '''Signal connections'''
        self.switch_dark.connect('state-set', self.toggle_dark)
        self.switch_notifications.connect('state-set', self.toggle_notifications)
        self.switch_temp.connect('state-set', self.toggle_temp)
        self.switch_release_candidate.connect('state-set', self.toggle_release_candidate)
        self.switch_versioning.connect('state-set', self.toggle_experimental_versioning)
        self.switch_installers.connect('state-set', self.toggle_experimental_installers)

        self.populate_dxvk_list()
        self.populate_runners_list()

    '''Toggle dark mode and store in user settings'''
    def toggle_dark(self, widget, state):
        self.settings.set_boolean("dark-theme", state)
        self.default_settings.set_property("gtk-application-prefer-dark-theme",
                                            state)

    def toggle_notifications(self, widget, state):
        self.settings.set_boolean("notifications", state)

    def toggle_release_candidate(self, widget, state):
        self.settings.set_boolean("release-candidate", state)
        self.populate_runners_list()

    def toggle_temp(self, widget, state):
        self.settings.set_boolean("temp", state)

    def toggle_experimental_versioning(self, widget, state):
        self.settings.set_boolean("experiments-versioning", state)
        self.window.btn_versioning.set_visible(
            self.settings.get_boolean("experiments-versioning"))

    def toggle_experimental_installers(self, widget, state):
        self.settings.set_boolean("experiments-installers", state)
        self.window.btn_installers.set_visible(
            self.settings.get_boolean("experiments-installers"))

    def populate_dxvk_list(self):
        for dxvk in self.runner.supported_dxvk.items():
            self.list_dxvk.add(BottlesDxvkEntry(self.window, dxvk))

    def populate_runners_list(self):
        for w in self.list_runners:
            if w != self.actionrow_prerelease:
                w.destroy()

        for runner in self.runner.supported_wine_runners.items():
            if (not self.window.settings.get_boolean("release-candidate")
                    and runner[1]["Channel"] in ["rc", "unstable"]):
                continue
            self.list_runners.add(BottlesRunnerEntry(self.window, runner))

        for runner in self.runner.supported_proton_runners.items():
            if (not self.window.settings.get_boolean("release-candidate")
                    and runner[1]["Channel"] in ["rc", "unstable"]):
                continue
            self.list_runners.add(BottlesRunnerEntry(self.window, runner))

@Gtk.Template(resource_path='/com/usebottles/bottles/dxvk-entry.ui')
class BottlesDxvkEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesDxvkEntry'

    '''Get widgets from template'''
    btn_download = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    box_download_status = Gtk.Template.Child()
    label_download_status = Gtk.Template.Child()

    def __init__(self, window, dxvk, **kwargs):
        super().__init__(**kwargs)

        '''Init template'''
        self.init_template()

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.dxvk_name = dxvk[0]

        '''Populate widgets'''
        self.set_title(self.dxvk_name)

        if dxvk[1].get("Installed"):
            self.btn_browse.set_visible(True)
        else:
            self.btn_download.set_visible(True)
            self.btn_browse.set_visible(False)


        '''Signal connections'''
        self.btn_download.connect('pressed', self.download_dxvk)
        self.btn_browse.connect('pressed', self.run_browse)

    '''Install dxvk'''
    def download_dxvk(self, widget):
        self.btn_download.set_visible(False)
        self.box_download_status.set_visible(True)
        self.runner.install_component("dxvk", self.dxvk_name, func=self.update_status)

    '''Browse dxvk files'''
    def run_browse(self, widget):
        self.btn_download.set_visible(False)
        self.runner.open_filemanager(path_type="dxvk",
                                     dxvk=self.dxvk_name)

    def idle_update_status(self, count=False, block_size=False, total_size=False, completed=False, failed=False):
        if failed:
            self.box_download_status.set_visible(False)
            self.btn_download.set_visible(True)
            self.btn_browse.set_visible(False)
            return False

        if not self.label_download_status.get_visible():
            self.label_download_status.set_visible(True)

        if not completed:
            percent = int(count * block_size * 100 / total_size)
            self.label_download_status.set_text(f'{str(percent)}%')
        else:
            percent = 100

        if percent == 100:
            self.box_download_status.set_visible(False)
            self.btn_browse.set_visible(True)

    def update_status(self, count=False, block_size=False, total_size=False, completed=False, failed=False):
        GLib.idle_add(self.idle_update_status, count, block_size, total_size, completed, failed)


@Gtk.Template(resource_path='/com/usebottles/bottles/runner-entry.ui')
class BottlesRunnerEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesRunnerEntry'

    '''Get widgets from template'''
    btn_download = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    box_download_status = Gtk.Template.Child()
    label_download_status = Gtk.Template.Child()

    def __init__(self, window, runner_entry, **kwargs):
        super().__init__(**kwargs)

        '''Init template'''
        self.init_template()

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.runner_name = runner_entry[0]

        '''Populate widgets'''
        self.set_title(self.runner_name)

        if runner_entry[1].get("Installed"):
            self.btn_browse.set_visible(True)
        else:
            self.btn_download.set_visible(True)
            self.btn_browse.set_visible(False)

        '''Signal connections'''
        self.btn_download.connect('pressed', self.download_runner)
        self.btn_browse.connect('pressed', self.run_browse)

    '''Install runner'''
    def download_runner(self, widget):
        self.btn_download.set_visible(False)
        self.box_download_status.set_visible(True)

        component_type = "runner"
        if self.runner_name.lower().startswith("proton"):
            component_type = "runner:proton"

        self.runner.install_component(component_type,
                                      self.runner_name,
                                      func=self.update_status)

    '''Browse runner files'''
    def run_browse(self, widget):
        self.btn_download.set_visible(False)
        self.runner.open_filemanager(path_type="runner",
                                     runner=self.runner_name)

    def idle_update_status(self, count=False, block_size=False, total_size=False, completed=False, failed=False):
        if failed:
            self.box_download_status.set_visible(False)
            self.btn_download.set_visible(True)
            self.btn_browse.set_visible(False)
            return False

        if not self.label_download_status.get_visible():
            self.label_download_status.set_visible(True)

        if not completed:
            percent = int(count * block_size * 100 / total_size)
            self.label_download_status.set_text(f'{str(percent)}%')
        else:
            percent = 100

        if percent == 100:
            self.box_download_status.set_visible(False)
            self.btn_browse.set_visible(True)

    def update_status(self, count=False, block_size=False, total_size=False, completed=False, failed=False):
        GLib.idle_add(self.idle_update_status, count, block_size, total_size, completed, failed)

