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

from gi.repository import Gtk

@Gtk.Template(resource_path='/com/usebottles/bottles/runner-entry.ui')
class BottlesRunnerEntry(Gtk.Box):
    __gtype_name__ = 'BottlesRunnerEntry'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    label_name = Gtk.Template.Child()
    btn_download = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    spinner_installation = Gtk.Template.Child()

    def __init__(self, window, runner_name, installable=False, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Set runner type based on name, also if runner is proton then
        add suffix `Proton-`.
        '''
        if not runner_name.lower().startswith(("lutris", "proton", "dxvk")):
            self.runner_type = "runner:proton"
            runner_name = "Proton-%s" % runner_name
        else:
            self.runner_type = "runner"

        '''
        Set reusable variables
        '''
        self.window = window
        self.runner = window.runner
        self.runner_name = runner_name

        '''
        Set runner name to the label
        '''
        self.label_name.set_text(runner_name)

        '''
        Connect signals to widgets
        '''
        self.btn_download.connect('pressed', self.download_runner)
        self.btn_browse.connect('pressed', self.run_browse)

        if installable:
            self.runner_tag = installable[0]
            self.runner_file = installable[1]
            self.btn_download.set_visible(True)
            self.btn_browse.set_visible(False)

    def download_runner(self, widget):
        self.btn_download.set_visible(False)
        self.spinner_installation.set_visible(True)
        self.runner.install_component(self.runner_type,
                                      self.runner_tag,
                                      self.runner_file)

    def run_browse(self, widget):
        self.runner.open_filemanager(path_type="runner",
                                     runner=self.runner_name)

@Gtk.Template(resource_path='/com/usebottles/bottles/dxvk-entry.ui')
class BottlesDxvkEntry(Gtk.Box):
    __gtype_name__ = 'BottlesDxvkEntry'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    label_name = Gtk.Template.Child()
    btn_download = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    spinner_installation = Gtk.Template.Child()

    def __init__(self, window, dxvk_name, installable=False, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        if not dxvk_name.lower().startswith("dxvk"):
            dxvk_name = "dxvk-%s" % dxvk_name[1:]

        '''
        Set reusable variables
        '''
        self.window = window
        self.runner = window.runner
        self.dxvk_name = dxvk_name

        '''
        Set dxvk name to the label
        '''
        self.label_name.set_text(dxvk_name)

        '''
        Connect signals to widgets
        '''
        self.btn_download.connect('pressed', self.download_dxvk)
        self.btn_browse.connect('pressed', self.run_browse)

        if installable:
            self.dxvk_tag = installable[0]
            self.dxvk_file = installable[1]
            self.btn_download.set_visible(True)
            self.btn_browse.set_visible(False)

    def download_dxvk(self, widget):
        self.runner.install_component("dxvk",
                                      self.dxvk_tag,
                                      self.dxvk_file)

    def run_browse(self, widget):
        self.btn_download.set_visible(False)
        self.spinner_installation.set_visible(True)
        self.runner.open_filemanager(path_type="dxvk",
                                     dxvk=self.dxvk_name)


@Gtk.Template(resource_path='/com/usebottles/bottles/preferences.ui')
class BottlesPreferences(Gtk.Box):
    __gtype_name__ = 'BottlesPreferences'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    notebook_preferences = Gtk.Template.Child()
    switch_notifications = Gtk.Template.Child()
    switch_temp = Gtk.Template.Child()
    switch_release_candidate = Gtk.Template.Child()
    combo_views = Gtk.Template.Child()
    list_runners = Gtk.Template.Child()
    list_dxvk = Gtk.Template.Child()
    btn_runner_updates = Gtk.Template.Child()
    btn_dxvk_updates = Gtk.Template.Child()

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Common variables
        '''
        self.window = window
        self.settings = window.settings

        '''
        Connect signals to widgets
        '''
        self.switch_notifications.connect('state-set', self.toggle_notifications)
        self.switch_temp.connect('state-set', self.toggle_temp)
        self.switch_release_candidate.connect('state-set', self.toggle_release_candidate)
        self.combo_views.connect('changed', self.change_startup_view)
        self.btn_runner_updates.connect('pressed', self.get_runner_updates)
        self.btn_dxvk_updates.connect('pressed', self.get_dxvk_updates)

        '''
        Set widgets status from user settings
        '''
        self.switch_notifications.set_active(self.settings.get_boolean("notifications"))
        self.switch_temp.set_active(self.settings.get_boolean("temp"))
        self.switch_release_candidate.set_active(self.settings.get_boolean("release-candidate"))
        self.combo_views.set_active_id(self.settings.get_string("startup-view"))

        '''
        Run methods
        '''
        self.update_runners()
        self.update_dxvk()

    '''
    Set dummy runner alerting user for no installed runners
    '''
    def set_dummy_runner(self):
        for runner in self.list_runners.get_children(): runner.destroy()
        message = _("No installed runners, installing latest release ..\nYou'll be able to create bottles when I'm done.")
        self.list_runners.add(BottlesRunnerEntry(self.window, message))

    '''
    Get runners updates
    '''
    def get_runner_updates(self,widget):
        self.update_runners()
        for runner in self.window.runner.get_runner_updates().items():
            rc = "rc" in runner[0].lower()
            if rc and self.settings.get_boolean("release-candidate") or not rc:
                self.list_runners.add(BottlesRunnerEntry(self.window,
                                                         runner[0],
                                                         installable=runner))

    '''
    Get dxvk updates
    '''
    def get_dxvk_updates(self,widget):
        self.update_dxvk()
        for dxvk in self.window.runner.get_dxvk_updates().items():
            self.list_dxvk.add(BottlesDxvkEntry(self.window,
                                                 dxvk[0],
                                                 installable=dxvk))

    '''
    Add runners to the list_runners
    '''
    def update_runners(self):
        for runner in self.list_runners.get_children(): runner.destroy()

        for runner in self.window.runner.runners_available:
            self.list_runners.add(BottlesRunnerEntry(self.window, runner))

    '''
    Add dxvk to the list_dxvk
    '''
    def update_dxvk(self):
        for dxvk in self.list_dxvk.get_children(): dxvk.destroy()

        for dxvk in self.window.runner.dxvk_available:
            self.list_dxvk.add(BottlesDxvkEntry(self.window, dxvk))

    '''
    Toggle notifications and store status in settings
    '''
    def toggle_notifications(self, widget, state):
        self.settings.set_boolean("notifications", state)

    '''
    Toggle Release Candidate for Runners
    '''
    def toggle_release_candidate(self, widget, state):
        self.settings.set_boolean("release-candidate", state)

    '''
    Toggle temp cleaner and store status in settings
    '''
    def toggle_temp(self, widget, state):
        self.settings.set_boolean("temp", state)

    '''
    Change the startup view and save in user settings
    '''
    def change_startup_view(self, widget):
        option = widget.get_active_id()
        self.settings.set_string("startup-view", option)
        
