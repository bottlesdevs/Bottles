# envvars.py
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


@Gtk.Template(resource_path='/com/usebottles/bottles/exclusion-pattern-entry.ui')
class ExclusionPatternEntry(Adw.ActionRow):
    __gtype_name__ = 'ExclusionPatternEntry'

    # region Widgets
    btn_remove = Gtk.Template.Child()
    # endregion

    def __init__(self, parent, pattern, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.manager = parent.window.manager
        self.config = parent.config
        self.pattern = pattern

        self.set_title(self.pattern)

        # connect signals
        self.btn_remove.connect("clicked", self.__remove)

    def __remove(self, *_args):
        """
        Remove the env var from the bottle configuration and
        destroy the widget
        """
        patterns = self.config.Versioning_Exclusion_Patterns
        if self.pattern in patterns:
            patterns.remove(self.pattern)

        self.manager.update_config(
            config=self.config,
            key="Versioning_Exclusion_Patterns",
            value=patterns
        )
        self.parent.group_patterns.remove(self)


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-exclusion-patterns.ui')
class ExclusionPatternsDialog(Adw.Window):
    __gtype_name__ = 'ExclusionPatternsDialog'

    # region Widgets
    entry_name = Gtk.Template.Child()
    group_patterns = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.__populate_patterns_list()

        # connect signals
        self.entry_name.connect("apply", self.__save_var)

    def __save_var(self, *_args):
        """
        This function save the new env var to the
        bottle configuration
        """
        pattern = self.entry_name.get_text()
        self.manager.update_config(
            config=self.config,
            key="Versioning_Exclusion_Patterns",
            value=self.config.Versioning_Exclusion_Patterns + [pattern]
        )
        _entry = ExclusionPatternEntry(self, pattern)
        GLib.idle_add(self.group_patterns.add, _entry)
        self.entry_name.set_text("")

    def __populate_patterns_list(self):
        """
        This function populate the list of exclusion patterns
        with the existing ones from the bottle configuration
        """
        patterns = self.config.Versioning_Exclusion_Patterns
        if len(patterns) == 0:
            self.group_patterns.set_description(_("No exclusion patterns defined."))
            return

        self.group_patterns.set_description("")
        for pattern in patterns:
            _entry = ExclusionPatternEntry(self, pattern)
            GLib.idle_add(self.group_patterns.add, _entry)
