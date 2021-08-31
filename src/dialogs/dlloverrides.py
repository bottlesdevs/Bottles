# details.py
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

@Gtk.Template(resource_path='/com/usebottles/bottles/dll-override-entry.ui')
class DLLEntry(Handy.ActionRow):
    __gtype_name__ = 'DLLEntry'

    # region Widgets
    btn_remove = Gtk.Template.Child()
    combo_type = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, override, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.override = override

        '''Populate widgets'''
        self.set_title(self.override[0])
        self.combo_type.set_active_id(self.override[1])

        # connect signals
        self.btn_remove.connect('pressed', self.remove_override)
        self.combo_type.connect('changed', self.set_override_type)

    def set_override_type(self, widget):
        override_type = widget.get_active_id()
        self.manager.update_config(config=self.config,
                                         key=self.override[0],
                                         value=override_type,
                                         scope="DLL_Overrides")

    '''Remove DLL override'''
    def remove_override(self, widget):
        '''Remove override from bottle config'''
        self.manager.update_config(config=self.config,
                                         key=self.override[0],
                                         value=False,
                                         scope="DLL_Overrides",
                                         remove=True)

        '''Remove entry from list_overrides'''
        self.destroy()

@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-dll-overrides.ui')
class DLLOverridesDialog(Handy.Window):
    __gtype_name__ = 'DLLOverridesDialog'

    # region Widgets
    entry_name = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    list_overrides = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        '''Populate widgets'''
        self.populate_overrides_list()

        # connect signals
        self.btn_save.connect('pressed', self.save_override)

    '''Save new DLL override'''
    def idle_save_override(self, widget=False):
        dll_name = self.entry_name.get_text()

        if dll_name !=  "":
            '''Store new override in bottle config'''
            self.manager.update_config(config=self.config,
                                             key=dll_name,
                                             value="n,b",
                                             scope="DLL_Overrides")

            '''Create new entry in list_overrides'''
            self.list_overrides.add(DLLEntry(self.window,
                                                            self.config,
                                                            [dll_name, "n,b"]))
            '''Empty entry_name'''
            self.entry_name.set_text("")

    def save_override(self,widget=False):
        GLib.idle_add(self.idle_save_override)

    def idle_populate_overrides_list(self):
        for override in self.config.get("DLL_Overrides").items():
            self.list_overrides.add(DLLEntry(self.window,
                                                            self.config,
                                                            override))

    def populate_overrides_list(self):
        GLib.idle_add(self.idle_populate_overrides_list)