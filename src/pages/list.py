# window.py
#
# Copyright 2020 mirkobrombin
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

@Gtk.Template(resource_path='/pm/mirko/bottles/list-entry.ui')
class BottlesListEntry(Gtk.Box):
    __gtype_name__ = 'BottlesListEntry'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()


@Gtk.Template(resource_path='/pm/mirko/bottles/list.ui')
class BottlesList(Gtk.Box):
    __gtype_name__ = 'BottlesList'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    list_scrolled_window = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        self.list_scrolled_window.add(BottlesListEntry())
