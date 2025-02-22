# installer_dialog.py
#
# Copyright 2025 The Bottles Contributors
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

import urllib.request

from gettext import gettext as _
from gi.repository import Gtk, GLib, Gio, GdkPixbuf, Adw

from bottles.backend.utils.threading import RunAsync
from bottles.frontend.gtk import GtkUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/local-resource-row.ui")
class LocalResourceRow(Adw.ActionRow):
    __gtype_name__ = "LocalResourceRow"

    # region Widgets
    btn_path = Gtk.Template.Child()

    # endregion

    def __init__(self, parent, resource, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.resource = resource

        self.set_title(resource)

        # connect signals
        self.btn_path.connect("clicked", self.__choose_path)

    def __choose_path(self, *_args):
        """
        Open the file chooser dialog and set the path to the
        selected file
        """

        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = dialog.get_file().get_path()
            self.parent.add_resource(self.resource, path)
            self.set_subtitle(path)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Resource File"),
            action=Gtk.FileChooserAction.OPEN,
            parent=self.parent,
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()


@Gtk.Template(resource_path="/com/usebottles/bottles/installer-dialog.ui")
class InstallerDialog(Adw.Window):
    __gtype_name__ = "InstallerDialog"
    __sections = {}
    __steps = 0
    __current_step = 0
    __local_resources = []
    __final_resources = {}

    # region widgets
    stack = Gtk.Template.Child()
    window_title = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_proceed = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    status_init = Gtk.Template.Child()
    status_installed = Gtk.Template.Child()
    status_error = Gtk.Template.Child()
    progressbar = Gtk.Template.Child()
    group_resources = Gtk.Template.Child()
    install_status_page = Gtk.Template.Child()
    img_icon = Gtk.Template.Child()
    img_icon_install = Gtk.Template.Child()
    style_provider = Gtk.CssProvider()

    # endregion

    def __init__(self, window, config, installer, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        self.window = window
        self.manager = window.manager
        self.config = config
        self.installer = installer

        self.__steps_phrases = {
            "deps": _("Installing Windows dependencies…"),
            "params": _("Configuring the bottle…"),
            "steps": _("Processing installer steps…"),
            "exe": _("Installing the {}…".format(installer[1].get("Name"))),
            "checks": _("Performing final checks…"),
        }

        self.status_init.set_title(installer[1].get("Name"))
        self.install_status_page.set_title(
            _("Installing {0}…").format(installer[1].get("Name"))
        )
        self.status_installed.set_description(
            _("{0} is now available in the programs view.").format(
                installer[1].get("Name")
            )
        )
        self.__set_icon()

        self.btn_install.connect("clicked", self.__check_resources)
        self.btn_proceed.connect("clicked", self.__install)
        self.btn_close.connect("clicked", self.__close)

    def __set_icon(self):
        try:
            url = self.manager.installer_manager.get_icon_url(self.installer[0])
            if url is None:
                self.img_icon.set_visible(False)
                self.img_icon_install.set_visible(False)
                return

            with urllib.request.urlopen(url) as res:
                stream = Gio.MemoryInputStream.new_from_data(res.read(), None)
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream(stream, None)
                self.img_icon.set_pixel_size(78)
                self.img_icon.set_from_pixbuf(pixbuf)
                self.img_icon_install.set_pixel_size(78)
                self.img_icon_install.set_from_pixbuf(pixbuf)
        except:
            self.img_icon.set_visible(False)
            self.img_icon_install.set_visible(False)

    def __check_resources(self, *_args):
        self.__local_resources = self.manager.installer_manager.has_local_resources(
            self.installer
        )
        if len(self.__local_resources) == 0:
            self.__install()
            return

        for resource in self.__local_resources:
            _entry = LocalResourceRow(self, resource)
            GLib.idle_add(self.group_resources.add, _entry)

        self.btn_proceed.set_visible(True)
        self.stack.set_visible_child_name("page_resources")

    def __install(self, *_args):
        self.set_deletable(False)
        self.stack.set_visible_child_name("page_install")

        @GtkUtils.run_in_main_loop
        def set_status(result, error=False):
            if result.ok:
                return self.__installed()
            _err = result.data.get("message", _("Installer failed with unknown error"))
            self.__error(_err)

        self.set_steps(self.manager.installer_manager.count_steps(self.installer))

        RunAsync(
            task_func=self.manager.installer_manager.install,
            callback=set_status,
            config=self.config,
            installer=self.installer,
            step_fn=self.next_step,
            local_resources=self.__final_resources,
        )

    def __installed(self):
        self.set_deletable(False)
        self.stack.set_visible_child_name("page_installed")
        self.window.page_details.details_view_subpage.view_bottle.update_programs()

    def __error(self, error):
        self.set_deletable(True)
        self.status_error.set_description(error)
        self.stack.set_visible_child_name("page_error")

    def next_step(self):
        """Next step"""
        phrase = self.__steps_phrases[self.__sections[self.__current_step]]
        self.progressbar.set_text(phrase)
        self.__current_step += 1
        self.progressbar.set_fraction(self.__current_step * (1 / self.__steps))

    def set_steps(self, steps):
        """Set steps"""
        self.__steps = steps["total"]
        self.__sections = steps["sections"]

    def add_resource(self, resource, path):
        self.__final_resources[resource] = path
        if len(self.__local_resources) == len(self.__final_resources):
            self.btn_proceed.set_sensitive(True)

    def __close(self, *_args):
        self.destroy()
