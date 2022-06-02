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

from gi.repository import Gtk, GLib, Adw
from gettext import gettext as _
import webbrowser

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.dialogs.generic import SourceDialog


@Gtk.Template(resource_path='/com/usebottles/bottles/installer-entry.ui')
class InstallerEntry(Adw.ActionRow):
    __gtype_name__ = 'InstallerEntry'

    # region Widgets
    btn_install = Gtk.Template.Child()
    btn_review = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    btn_report = Gtk.Template.Child()
    img_installed = Gtk.Template.Child()
    img_error = Gtk.Template.Child()
    label_step = Gtk.Template.Child()
    label_grade = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, installer, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.installer = installer
        self.spinner = Gtk.Spinner()
        self.__step = 0
        self.steps = 0
        name = installer[1].get("Name")
        description = installer[1].get("Description")
        grade = installer[1].get('Grade')

        # populate widgets
        self.set_title(name)
        self.set_subtitle(description)
        self.label_grade.set_text(grade)
        self.label_grade.get_style_context().add_class(f"grade-{grade}")

        # connect signals
        self.btn_install.connect("clicked", self.__execute_installer)
        self.btn_manifest.connect("clicked", self.__open_manifest)
        self.btn_review.connect("clicked", self.__open_review)
        self.btn_report.connect("clicked", self.__open_bug_report)

    def __open_manifest(self, widget):
        """Open installer manifest"""
        plain_manifest = self.manager.installer_manager.get_installer(
            installer_name=self.installer[0],
            plain=True
        )
        SourceDialog(
            parent=self.window,
            title=_("Manifest for {0}").format(self.installer[0]),
            message=plain_manifest
        ).present()

    def __open_review(self, widget):
        """Open review"""
        plain_text = self.manager.installer_manager.get_review(self.installer[0], parse=False)
        SourceDialog(
            parent=self.window,
            title=_("Review for {0}").format(self.installer[0]),
            message=plain_text,
            lang="markdown"
        ).present()

    @staticmethod
    def __open_bug_report(widget):
        """Open bug report"""
        webbrowser.open("https://github.com/bottlesdevs/programs/issues")

    def __execute_installer(self, widget):
        """Execute installer"""
        def set_status(result, error=False):
            if result.status:
                return self.set_installed()
            _err = result.data.get("message", _("Installer failed with unknown error"))
            self.set_err(_err)
        self.set_steps(
            self.manager.installer_manager.count_steps(self.installer)
        )
        self.get_parent().set_sensitive(False)
        self.label_step.set_visible(True)
        while widget.get_first_child():
            widget.remove(widget.get_first_child())

        widget.set_sensitive(False)
        widget.add(self.spinner)

        self.spinner.show()
        GLib.idle_add(self.spinner.start)

        RunAsync(
            task_func=self.manager.installer_manager.install,
            callback=set_status,
            config=self.config,
            installer=self.installer,
            step_fn=self.next_step
        )

    def set_installed(self):
        """Set installed status"""
        self.spinner.stop()
        self.btn_install.set_visible(False)
        self.label_step.set_visible(False)
        self.img_installed.set_visible(True)
        self.get_parent().set_sensitive(True)
        self.window.page_details.update_programs()

    def set_err(self, msg="Something went wrong"):
        """Set error status"""
        self.spinner.stop()
        self.btn_install.set_visible(False)
        self.img_error.set_visible(True)
        self.label_step.set_visible(False)
        self.img_error.set_tooltip_text(msg)
        self.get_parent().set_sensitive(True)

    def next_step(self):
        """Next step"""
        self.__step += 1
        self.label_step.set_text(
            _(f"Step {self.__step} of {self.steps}")
        )

    def set_steps(self, steps):
        """Set steps"""
        self.steps = steps
