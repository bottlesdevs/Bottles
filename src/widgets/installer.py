# installer.py
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
from gettext import gettext as _
import webbrowser
from ..utils import RunAsync
from ..dialogs.generic import Dialog


@Gtk.Template(resource_path='/com/usebottles/bottles/installer-entry.ui')
class InstallerEntry(Handy.ActionRow):
    __gtype_name__ = 'InstallerEntry'

    # region Widgets
    btn_install = Gtk.Template.Child()
    btn_review = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    btn_report = Gtk.Template.Child()
    img_installed = Gtk.Template.Child()
    label_step = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, installer, plain=False, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.installer = installer
        self.spinner = Gtk.Spinner()
        self.__step = 0
        self.steps = 0

        # populate widgets
        self.set_title(installer[0])
        self.set_subtitle(installer[1].get("Description"))

        # connect signals
        self.btn_install.connect('pressed', self.__execute_installer)
        self.btn_manifest.connect('pressed', self.__open_manifest)
        self.btn_review.connect('pressed', self.__open_review)
        self.btn_report.connect('pressed', self.__open_bug_report)

    def __open_manifest(self, widget):
        '''Open installer manifest'''
        plain_manifest = self.manager.installer_manager.get_installer(
            installer_name=self.installer[0],
            installer_category=self.installer[1]["Category"],
            plain=True
        )
        dialog = Dialog(
            parent=self.window,
            title=_("Manifest for {0}").format(self.installer[0]),
            message=False,
            log=plain_manifest
        )
        dialog.run()
        dialog.destroy()

    def __open_review(self, widget):
        '''Open review'''
        html_review = self.manager.installer_manager.get_review(
            installer_name=self.installer[0],
        )
        dialog = Dialog(
            parent=self.window,
            title=_("Review for {0}").format(self.installer[0]),
            message=False,
            log=False,
            html=html_review
        )
        dialog.run()
        dialog.destroy()


    def __open_bug_report(self, widget):
        '''Open bug report'''
        webbrowser.open("https://github.com/bottlesdevs/programs/issues")

    def __execute_installer(self, widget):
        '''Execute installer'''
        self.get_parent().set_sensitive(False)
        self.label_step.set_visible(True)
        for w in widget.get_children():
            w.destroy()

        widget.set_sensitive(False)
        widget.add(self.spinner)

        self.spinner.show()
        GLib.idle_add(self.spinner.start)

        RunAsync(
            task_func=self.manager.installer_manager.install,
            config=self.config,
            installer=self.installer,
            widget=self
        )

    def set_installed(self):
        '''Set installed status'''
        self.spinner.stop()
        self.btn_install.set_visible(False)
        self.label_step.set_visible(False)
        self.img_installed.set_visible(True)
        self.get_parent().set_sensitive(True)

    def next_step(self):
        '''Next step'''
        self.__step += 1
        self.label_step.set_text(
            _(f"Step {self.__step} of {self.steps}")
        )

    def set_steps(self, steps):
        '''Set steps'''
        self.steps = steps
