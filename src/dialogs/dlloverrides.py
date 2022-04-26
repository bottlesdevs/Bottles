# dlloverrides.py
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

from gi.repository import Gtk, GLib, Adw


@Gtk.Template(resource_path='/com/usebottles/bottles/dll-override-entry.ui')
class DLLEntry(Adw.ActionRow):
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

        '''
        Set the DLL name as ActionRow title and set the
        combo_type to the type of override
        '''
        self.set_title(self.override[0])
        self.combo_type.set_active_id(self.override[1])

        # connect signals
        self.btn_remove.connect("clicked", self.__remove_override)
        self.combo_type.connect('changed', self.__set_override_type)

        self.__prevent_scroll()

    def __set_override_type(self, widget):
        """
        Change the override type according to the selected
        and update the bottle configuration
        """
        override_type = widget.get_active_id()
        self.manager.update_config(
            config=self.config,
            key=self.override[0],
            value=override_type,
            scope="DLL_Overrides"
        )

    def __remove_override(self, widget):
        """
        Remove the override from the bottle configuration and
        destroy the widget
        """
        self.manager.update_config(
            config=self.config,
            key=self.override[0],
            value=False,
            scope="DLL_Overrides",
            remove=True
        )
        self.destroy()

    def __prevent_scroll(self):
        def no_action(widget, event):
            return True

        # self.combo_type.connect('scroll-event', no_action)


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-dll-overrides.ui')
class DLLOverridesDialog(Adw.Window):
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

        self.__populate_overrides_list()

        # connect signals
        self.btn_save.connect("clicked", self.__save_override)

    def __idle_save_override(self, widget=False):
        """
        This function check if the override name is not empty, then
        store it in the bottle configuration and add a new entry to
        the list. It also clear the entry field
        """
        dll_name = self.entry_name.get_text()

        if dll_name != "":
            self.manager.update_config(
                config=self.config,
                key=dll_name,
                value="n,b",
                scope="DLL_Overrides"
            )

            self.list_overrides.append(
                DLLEntry(
                    window=self.window,
                    config=self.config,
                    override=[dll_name, "n,b"]
                )
            )

            self.entry_name.set_text("")

    def __save_override(self, widget=False):
        GLib.idle_add(self.__idle_save_override)

    def __idle_populate_overrides_list(self):
        """
        This function populate the list of overrides
        with the existing overrides from the bottle configuration
        """
        for override in self.config.get("DLL_Overrides").items():
            self.list_overrides.append(
                DLLEntry(
                    window=self.window,
                    config=self.config,
                    override=override
                )
            )

    def __populate_overrides_list(self):
        GLib.idle_add(self.__idle_populate_overrides_list)
