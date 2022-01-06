# bottle_installers.py
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

import os
from gettext import gettext as _
from gi.repository import Gtk

from ..utils import GtkUtils
from ..widgets.dependency import DependencyEntry


@Gtk.Template(resource_path='/com/usebottles/bottles/details-dependencies.ui')
class DependenciesView(Gtk.ScrolledWindow):
    __gtype_name__ = 'DetailsDependencies'

    # region Widgets
    list_dependencies = Gtk.Template.Child()
    btn_report = Gtk.Template.Child()
    btn_help = Gtk.Template.Child()
    entry_search_deps = Gtk.Template.Child()
    infobar_testing = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.btn_report.connect(
            "clicked", 
            GtkUtils.open_doc_url, 
            "contribute/missing-dependencies"
        )
        self.btn_help.connect(
            "clicked", GtkUtils.open_doc_url, "bottles/dependencies"
        )
        self.entry_search_deps.connect(
            'key-release-event', self.__search_dependencies
        )
        self.entry_search_deps.connect('changed', self.__search_dependencies)

        if "TESTING_REPOS" in os.environ and os.environ["TESTING_REPOS"] == "1":
            self.infobar_testing.set_visible(True)

    def __search_dependencies(self, widget, event=None, data=None):
        '''
        This function search in the list of dependencies the
        text written in the search entry.
        '''
        terms = widget.get_text()
        self.list_dependencies.set_filter_func(
            self.__filter_dependencies,
            terms
        )

    @staticmethod
    def __filter_dependencies(row, terms=None):
        text = row.get_title().lower() + row.get_subtitle().lower()
        if terms.lower() in text:
            return True
        return False

    def update(self, widget=False, config={}):
        '''
        This function update the dependencies list with the
        supported by the manager.
        '''
        self.config = config
        
        for w in self.list_dependencies:
            w.destroy()

        supported_dependencies = self.manager.supported_dependencies
        if len(supported_dependencies.keys()) > 0:
            for dep in supported_dependencies.items():
                if dep[0] in self.config.get("Installed_Dependencies"):
                    '''
                    If the dependency is already installed, do not
                    list it in the list. It will be listed in the
                    installed dependencies list.
                    '''
                    continue
                self.list_dependencies.add(
                    DependencyEntry(
                        window=self.window,
                        config=self.config,
                        dependency=dep
                    )
                )

        if len(self.config.get("Installed_Dependencies")) > 0:
            for dep in self.config.get("Installed_Dependencies"):
                plain = True
                if dep in supported_dependencies:
                    dep = (
                        dep,
                        supported_dependencies[dep]
                    )
                    plain = False

                self.list_dependencies.add(
                    DependencyEntry(
                        window=self.window,
                        config=self.config,
                        dependency=dep,
                        plain=plain
                    )
                )
