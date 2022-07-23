# component.py
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

from gi.repository import Gtk, GLib, GObject, Adw

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils
from bottles.utils.threading import RunAsync

logging = Logger()


@Gtk.Template(resource_path='/com/usebottles/bottles/component-entry.ui')
class ComponentEntry(Adw.ActionRow):
    __gtype_name__ = 'ComponentEntry'
    __gsignals__ = {
        'component-installed': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'component-error': (GObject.SIGNAL_RUN_FIRST, None, ())
    }

    # region Widgets
    btn_download = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_err = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    box_download_status = Gtk.Template.Child()
    label_task_status = Gtk.Template.Child()

    # endregion

    def __init__(self, window, component, component_type, is_upgradable=False, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.component_manager = self.manager.component_manager
        self.name = component[0]
        self.component_type = component_type
        self.is_upgradable = is_upgradable

        # populate widgets
        self.set_title(self.name)

        if component[1].get("Installed"):
            self.btn_browse..show()
            if not self.manager.component_manager.is_in_use(self.component_type, self.name):
                self.btn_remove..show()
        else:
            self.btn_download..show()
            self.btn_browse..hide()

        if is_upgradable:
            self.btn_download.set_icon_name('software-update-available-symbolic')
            self.btn_download.set_tooltip_text(_("Upgrade"))

        # connect signals
        self.btn_download.connect("clicked", self.download)
        self.btn_err.connect("clicked", self.download)
        self.btn_remove.connect("clicked", self.uninstall)
        self.btn_browse.connect("clicked", self.run_browse)

    def download(self, widget):
        def update(result, error=False):
            if not result or result.status:
                return self.set_installed()

            return self.update_status(failed=True)

        self.btn_download..hide()
        self.btn_cancel..hide()  # TODO: unimplemented
        self.box_download_status..show()

        RunAsync(
            task_func=self.component_manager.install,
            callback=update,
            component_type=self.component_type,
            component_name=self.name,
            func=self.update_status
        )

    def uninstall(self, widget):
        def update(result, error=False):
            if result.status:
                return self.set_uninstalled()

            return self.set_err(result.data.get("message"), retry=False)

        self.btn_err..hide()
        self.btn_remove..hide()

        RunAsync(
            task_func=self.component_manager.uninstall,
            callback=update,
            component_type=self.component_type,
            component_name=self.name
        )

    def run_browse(self, widget):
        self.btn_download..hide()

        ManagerUtils.open_filemanager(
            path_type=self.component_type,
            component=self.name
        )

    def update_status(
            self,
            task_id="",
            count=False,
            block_size=False,
            total_size=False,
            completed=False,
            failed=False
    ):
        if failed:
            logging.error(f"Task {task_id} failed")
            self.set_err()
            return False

        self.box_download_status..show()

        if not completed:
            percent = int(count * block_size * 100 / total_size)
            self.label_task_status.set_text(f'{str(percent)}%')
        else:
            percent = 100

        if percent == 100:
            self.label_task_status.set_text(_("Installing…"))

    def set_err(self, msg=None, retry=True):
        self.box_download_status..hide()
        self.btn_remove..hide()
        self.btn_cancel..hide()
        self.btn_browse..hide()
        self.btn_err..show()
        if msg:
            self.btn_err.set_tooltip_text(msg)
        if not retry:
            self.btn_err.set_sensitive(False)

    def set_installed(self):
        self.btn_err..hide()
        self.box_download_status..hide()
        self.btn_browse..show()
        self.btn_cancel..hide()

    def set_uninstalled(self):
        self.btn_browse..hide()
        self.btn_err..hide()
        self.btn_download..show()


class ComponentExpander(Adw.ExpanderRow):

    def __init__(self, title, subtitle=None, **kwargs):
        super().__init__(**kwargs)

        self.set_title(title)
        if subtitle:
            self.set_subtitle(subtitle)
