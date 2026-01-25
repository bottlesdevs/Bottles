# funding.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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

import webbrowser
from gettext import gettext as _

from gi.repository import Adw, GObject, Gtk


class FundingDialog(Adw.Window):
    __gsignals__ = {
        "response": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self, parent, **kwargs):
        super().__init__(modal=True, transient_for=parent)
        self.set_default_size(600, 500)
        self.set_title(_("Support Bottles"))
        
        self.connect("close-request", self.__on_close_request)
        self._response = "close"

        content = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_title(False)
        content.add_top_bar(header)
        status_page = Adw.StatusPage()
        status_page.set_icon_name("heart-symbolic")
        status_page.set_title(_("Do you like Bottles?"))
        status_page.set_description(
            _(
                "With over 3 million installations, Bottles is built by and for its community."
                "\nA donation today helps secure its future and keep it truly independent."
            )
        )

        btns_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btns_box.set_halign(Gtk.Align.CENTER)

        if kwargs.get("show_dont_show", False):
            btn_secondary = Gtk.Button(label=_("Don't Show Again"))
            btn_secondary.add_css_class("destructive-action")
            btn_secondary.connect("clicked", self.on_dont_show_clicked)
        else:
            btn_secondary = Gtk.Button(label=_("Not Now"))
            btn_secondary.connect("clicked", lambda x: self.close())
        
        btn_secondary.add_css_class("pill")
        btn_secondary.set_size_request(180, -1)
        btns_box.append(btn_secondary)

        btn_donate = Gtk.Button(label=_("Donate"))
        btn_donate.add_css_class("pill")
        btn_donate.add_css_class("suggested-action")
        btn_donate.set_size_request(180, -1)
        btn_donate.connect("clicked", self.on_donate_clicked)
        btns_box.append(btn_donate)

        status_page.set_child(btns_box)
        content.set_content(status_page)
        self.set_content(content)

    def on_donate_clicked(self, btn):
        webbrowser.open_new_tab("https://usebottles.com/funding/")
        self._response = "donate"
        self.close()

    def on_dont_show_clicked(self, btn):
        self._response = "dismiss"
        self.close()
        
    def __on_close_request(self, *args):
        self.emit("response", self._response)
