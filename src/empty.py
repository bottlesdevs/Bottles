# download.py
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

@Gtk.Template(resource_path='/com/usebottles/bottles/empty.ui')
class BottlesEmpty(Gtk.Grid):
    __gtype_name__ = 'BottlesEmpty'

    '''Get widgets from template'''
    img_icon = Gtk.Template.Child()
    label_text = Gtk.Template.Child()
    label_tip = Gtk.Template.Child()

    def __init__(self, text=False, icon=False, tip=False, **kwargs):
        super().__init__(**kwargs)

        '''Init template'''
        try:
            self.init_template()
        except TypeError:
            self.init_template("")

        '''Populate widgets data'''
        if text:
            self.label_text.set_text(text)

        if icon:
            self.img_icon.set_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR)

        if tip:
            self.label_tip.set_visible(True)
            self.label_tip.set_text(tip)
