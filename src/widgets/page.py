# page.py
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


class PageRow(Gtk.ListBoxRow):

    def __init__(self, page_name, page, **kwargs):
        super().__init__(**kwargs)
        self.page_name = page_name

        icons = {
            "bottle": "com.usebottles.bottles-symbolic",
            "preferences": "applications-system-symbolic",
            "dependencies": "application-x-addon-symbolic",
            "programs": "preferences-desktop-apps-symbolic",
            "versioning": "preferences-system-time-symbolic",
            "installers": "system-software-install-symbolic",
            "taskmanager": "computer-symbolic-symbolic"
        }

        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        icon = Gtk.Image()
        icon.set_from_icon_name(icons[page_name], Gtk.IconSize.SMALL_TOOLBAR)
        box.pack_start(icon, False, False, 0)

        box.pack_start(
            Gtk.Label(
                label=page["title"],
                xalign=0.0
            ),
            False,
            False,
            0
        )

        self.get_style_context().add_class("page-row")

        self.add(box)

        self.show_all()
