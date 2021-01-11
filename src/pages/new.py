# add.py
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

import re, time

from gi.repository import Gtk, Handy

class BottlesEnvironmentRow(Gtk.ListBoxRow):

    def __init__(self, environment, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.environment = environment
        self.env_entry = BottlesEnvironmentEntry(environment)
        self.add(self.env_entry)

        self.set_visible(True)

    def get_environment_id(self):
        return self.environment.get("id")

    def select(self):
        return self.env_entry.show_selection()

    def deselect(self):
        return self.env_entry.hide_selection()

@Gtk.Template(resource_path='/com/usebottles/bottles/environment-entry.ui')
class BottlesEnvironmentEntry(Gtk.Box):
    __gtype_name__ = 'BottlesEnvironmentEntry'

    '''Get widgets from template'''
    label_title = Gtk.Template.Child()
    label_subtitle = Gtk.Template.Child()
    img_icon = Gtk.Template.Child()
    img_selected = Gtk.Template.Child()

    def __init__(self, environment, **kwargs):
        super().__init__(**kwargs)

        '''Init template'''
        self.init_template()

        '''Common variables'''
        self.environment = environment

        '''Populate'''
        self.label_title.set_text(environment.get("name"))
        self.label_subtitle.set_text(environment.get("description"))
        self.img_icon.set_from_icon_name(environment.get("icon"), Gtk.IconSize.SMALL_TOOLBAR)

        context = self.get_style_context()
        context.add_class(environment.get("id").lower())

        self.set_visible(True)

    def hide_selection(self):
        self.label_subtitle.set_visible(False)
        return self.img_selected.set_visible(False)

    def show_selection(self):
        self.label_subtitle.set_visible(True)
        return self.img_selected.set_visible(True)

@Gtk.Template(resource_path='/com/usebottles/bottles/new.ui')
class BottlesNew(Handy.Window):
    __gtype_name__ = 'BottlesNew'

    '''Get widgets from template'''
    stack_create = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    list_environments = Gtk.Template.Child()
    page_create = Gtk.Template.Child()
    page_creating = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    switch_versioning = Gtk.Template.Child()
    label_advanced = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    label_confirm = Gtk.Template.Child()
    box_advanced = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_dxvk = Gtk.Template.Child()
    progressbar_creating = Gtk.Template.Child()

    environments = [
        {
            "id": "Gaming",
            "name": _("Gaming"),
            "description": _("An environment improved for Windows games."),
            "icon": "applications-games-symbolic"
        },
        {
            "id": "Software",
            "name": _("Software"),
            "description": _("An environment for Windows software."),
            "icon": "applications-engineering-symbolic"
        },
        {
            "id": "Custom",
            "name": _("Custom"),
            "description": _("A clear environment for your experiments."),
            "icon": "applications-science-symbolic"
        }
    ]

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        '''Init template'''
        self.init_template()

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.selected_environment = "gaming"

        '''Signal connections'''
        self.btn_cancel.connect('pressed', self.close_window)
        self.btn_close.connect('pressed', self.close_window)
        self.btn_create.connect('pressed', self.create_bottle)
        self.list_environments.connect('row-selected', self.set_active_environment)
        self.entry_name.connect('key-release-event', self.check_entry_name)

        for environment in self.environments:
            env_row = BottlesEnvironmentRow(environment)
            self.list_environments.add(env_row)

        '''Select the first environment in list'''
        self.list_environments.select_row(
            self.list_environments.get_children()[0])

        '''Populate combo_runner'''
        for runner in self.runner.runners_available:
            self.combo_runner.append(runner, runner)

        self.combo_runner.set_active(0)

    def set_active_environment(self, widget, row):
        for w in self.list_environments.get_children():
            w.deselect()
        row.select()

        '''Set selected environment'''
        self.selected_environment = row.get_environment_id()

        '''Toggle advanced options'''
        status = True if row.get_environment_id() == "Custom" else False
        for w in [self.label_advanced, self.box_advanced]:
            w.set_visible(status)
            w.set_visible(status)

    '''Validate entry_name input'''
    def check_entry_name(self, widget, event_key):
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,]')
        name = widget.get_text()

        if(regex.search(name) == None) and name != "":
            self.btn_create.set_visible(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_create.set_visible(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    '''Create the bottle'''
    def create_bottle(self, widget):
        '''Change buttons state'''
        self.btn_cancel.set_sensitive(False)
        self.btn_create.set_visible(False)
        self.page_create.set_visible(False)

        '''Show the creating page'''
        self.stack_create.set_visible_child_name("page_creating")

        '''Create bottle
        TODO: add dxvk version'''
        versioning_state = self.switch_versioning.get_state()
        self.runner.create_bottle(name=self.entry_name.get_text(),
                                  path="",
                                  environment=self.selected_environment,
                                  runner=self.combo_runner.get_active_id(),
                                  versioning=versioning_state,
                                  dialog=self)

    '''Concatenate label_output'''
    def update_output(self, text):
        current_text = self.label_output.get_text()
        text = "{0}{1}\n".format(current_text, text)
        self.label_output.set_text(text)

    def finish(self):
        self.label_confirm.set_text(
            _("A bottle named “%s” was created successfully") % self.entry_name.get_text())

        self.btn_cancel.set_visible(False)
        self.btn_close.set_visible(True)

        self.stack_create.set_visible_child_name("page_created")

        '''Update bottles'''
        self.runner.check_bottles()
        self.window.page_list.update_bottles()

    '''Progressbar pulse every 1s'''
    def pulse(self):
        while True:
            time.sleep(1)
            self.progressbar_creating.pulse()

    '''Destroy the window'''
    def close_window(self, widget):
        self.destroy()
