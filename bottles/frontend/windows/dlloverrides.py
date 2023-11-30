# dlloverrides.py
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

from gi.repository import Gtk, GLib, Adw

from bottles.backend.dlls.dll import DLLComponent

@Gtk.Template(resource_path='/com/usebottles/bottles/dll-override-entry.ui')
class DLLEntry(Adw.ComboRow):
    __gtype_name__ = 'DLLEntry'

    # region Widgets
    btn_remove = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, override, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.override = override
        types = ("b", "n", "b,n", "n,b", "d")

        '''
        Set the DLL name as ActionRow title and set the
        combo_type to the type of override
        '''
        self.set_title(self.override[0])
        self.set_selected(types.index(self.override[1]))

        # connect signals
        self.btn_remove.connect("clicked", self.__remove_override)
        self.connect('notify::selected', self.__set_override_type)

    def __set_override_type(self, *_args):
        """
        Change the override type according to the selected
        and update the bottle configuration
        """
        selected = self.get_selected()
        types = ("b", "n", "b,n", "n,b", "d")
        self.manager.update_config(
            config=self.config,
            key=self.override[0],
            value=types[selected],
            scope="DLL_Overrides"
        )

    def __remove_override(self, *_args):
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
        self.get_parent().remove(self)


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-dll-overrides.ui')
class DLLOverridesDialog(Adw.PreferencesWindow):
    __gtype_name__ = 'DLLOverridesDialog'

    # region Widgets
    entry_row = Gtk.Template.Child()
    group_overrides = Gtk.Template.Child()
    menu_invalid_override = Gtk.Template.Child()

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
        self.entry_row.connect('changed', self.__check_override)
        self.entry_row.connect("apply", self.__save_override)

    def __check_override(self, *_args):
        """
        This function check if the override name is valid
        Overrides already managed by Bottles (e.g. DXVK, VKD3D...) are deemed invalid
        """
        dll_name = self.entry_row.get_text()
        invalid_dlls = []

        for managed_component in DLLComponent.__subclasses__():
            invalid_dlls += managed_component.get_override_keys().split(",")

        is_invalid = dll_name in invalid_dlls

        self.__valid_name = not is_invalid
        self.menu_invalid_override.set_visible(is_invalid)
        if is_invalid:
            self.entry_row.add_css_class("error")
            self.entry_row.set_show_apply_button(False)
        else:
            self.entry_row.remove_css_class("error")
        # Needs to be set to true immediately
        self.entry_row.set_show_apply_button(True)

    def __save_override(self, *_args):
        """
        This function check if the override name is not empty, then
        store it in the bottle configuration and add a new entry to
        the list. It also clears the entry field
        """
        dll_name = self.entry_row.get_text()

        if dll_name != "" and self.__valid_name:
            self.manager.update_config(
                config=self.config,
                key=dll_name,
                value="n,b",
                scope="DLL_Overrides"
            )
            _entry = DLLEntry(
                window=self.window,
                config=self.config,
                override=[dll_name, "n,b"]
            )
            GLib.idle_add(self.group_overrides.add, _entry)
            self.group_overrides.set_description("")
            self.entry_row.set_text("")

    def __populate_overrides_list(self):
        """
        This function populate the list of overrides
        with the existing overrides from the bottle configuration
        """
        overrides = self.config.DLL_Overrides.items()

        if len(overrides) == 0:
            self.group_overrides.set_description(_("No overrides found."))
            return

        self.group_overrides.set_description("")
        for override in overrides:
            _entry = DLLEntry(
                window=self.window,
                config=self.config,
                override=override
            )
            GLib.idle_add(self.group_overrides.add, _entry)
