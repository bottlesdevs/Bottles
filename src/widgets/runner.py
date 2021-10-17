# runner.py
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

from gi.repository import Gtk, GLib, Handy

from ..backend.runner import Runner


@Gtk.Template(resource_path='/com/usebottles/bottles/runner-entry.ui')
class RunnerEntry(Handy.ActionRow):
    __gtype_name__ = 'RunnerEntry'

    # region Widgets
    btn_download = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_err = Gtk.Template.Child()
    box_download_status = Gtk.Template.Child()
    label_task_status = Gtk.Template.Child()
    # endregion

    def __init__(self, window, runner_entry, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.component_manager = self.manager.component_manager
        self.runner_name = runner_entry[0]
        self.spinner = Gtk.Spinner()

        # populate widgets
        self.set_title(self.runner_name)

        if runner_entry[1].get("Installed"):
            self.btn_browse.set_visible(True)
        else:
            self.btn_download.set_visible(True)
            self.btn_browse.set_visible(False)

        # connect signals
        self.btn_download.connect('pressed', self.download_runner)
        self.btn_err.connect('pressed', self.download_runner)
        self.btn_browse.connect('pressed', self.run_browse)

    '''Install runner'''

    def download_runner(self, widget):
        self.btn_err.set_visible(False)
        self.btn_download.set_visible(False)
        self.box_download_status.set_visible(True)
        for w in self.box_download_status.get_children():
            w.set_visible(True)

        component_type = "runner"
        if self.runner_name.lower().startswith("proton"):
            component_type = "runner:proton"

        self.component_manager.install(
            component_type,
            self.runner_name,
            func=self.update_status,
            after=self.set_installed
        )

    '''Browse runner files'''

    def run_browse(self, widget):
        self.btn_download.set_visible(False)
        Runner().open_filemanager(path_type="runner", component=self.runner_name)

    def idle_update_status(
        self,
        count=False,
        block_size=False,
        total_size=False,
        completed=False,
        failed=False
    ):
        if failed:
            self.set_err()
            return False

        self.label_task_status.set_visible(True)

        if not completed:
            percent = int(count * block_size * 100 / total_size)
            self.label_task_status.set_text(f'{str(percent)}%')
        else:
            percent = 100

        if percent == 100:
            for w in self.box_download_status.get_children():
                w.set_visible(False)
            self.btn_err.set_visible(False)
            self.box_download_status.add(self.spinner)
            self.spinner.set_visible(True)
            self.spinner.start()

    def set_err(self):
        self.spinner.stop()
        self.box_download_status.set_visible(False)
        self.btn_remove.set_visible(False)
        self.btn_browse.set_visible(False)
        self.btn_err.set_visible(True)

    def set_installed(self):
        self.spinner.stop()
        self.btn_err.set_visible(False)
        self.box_download_status.set_visible(False)
        self.btn_browse.set_visible(True)

    def update_status(
        self,
        count=False,
        block_size=False,
        total_size=False,
        completed=False,
        failed=False
    ):
        GLib.idle_add(
            self.idle_update_status,
            count,
            block_size,
            total_size,
            completed,
            failed
        )
