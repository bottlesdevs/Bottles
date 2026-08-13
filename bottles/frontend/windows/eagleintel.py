# eagleintel.py
#
# Copyright 2026 mirkobrombin <brombin94@gmail.com>
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

from gettext import gettext as _

from gi.repository import Adw, GObject, Gtk


class EagleIntelDialog(Adw.Dialog):
    __gsignals__ = {
        "response": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self, parent):
        super().__init__()
        self.set_content_width(600)
        self.set_content_height(560)
        self.set_title(_("Eagle Intelligence"))
        self.connect("closed", self.__on_closed)

        icon_theme = Gtk.IconTheme.get_for_display(self.get_display())
        icon_theme.add_resource_path("/com/usebottles/bottles/icons")

        content = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_title(False)
        content.add_top_bar(header)

        status_page = Adw.StatusPage()
        status_page.set_icon_name("com.usebottles.eagle-symbolic")
        status_page.set_title(_("Eagle just got smarter"))
        status_page.set_description(
            _(
                "Eagle can now identify Windows programs using offline "
                "compatibility data from ProtonDB and winetricks, then suggest "
                "settings that helped other users.\n\nTo try it, open a bottle, "
                "select Analyze with Eagle, and choose an executable."
            )
        )

        button = Gtk.Button(label=_("Got It"))
        button.set_halign(Gtk.Align.CENTER)
        button.set_size_request(180, -1)
        button.add_css_class("pill")
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda _button: self.close())
        status_page.set_child(button)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(status_page)
        content.set_content(scrolled)
        self.set_child(content)

    def __on_closed(self, *_args):
        self.emit("response", "close")
