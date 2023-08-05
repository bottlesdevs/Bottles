# installer.py
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
#

from gi.repository import Gtk, Adw
from gettext import gettext as _
import webbrowser

from bottles.frontend.windows.generic import SourceDialog
from bottles.frontend.windows.installer import InstallerDialog


@Gtk.Template(resource_path='/com/usebottles/bottles/installer-entry.ui')
class InstallerEntry(Adw.ActionRow):
    __gtype_name__ = 'InstallerEntry'

    # region Widgets
    btn_install = Gtk.Template.Child()
    btn_review = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    btn_report = Gtk.Template.Child()
    label_grade = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, installer, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.installer = installer

        grade_descriptions = {
            "Bronze": _("This application may work poorly. The installer was configured to provide the best possible experience, but expect glitches, instability and lack of working features."),
            "Silver": _("This program works with noticeable glitches, but these glitches do not affect the application's functionality."),
            "Gold": _("This program works with minor glitches."),
            "Platinum": _("This program works perfectly."),
        }

        name = installer[1].get("Name")
        description = installer[1].get("Description")
        grade = installer[1].get('Grade')
        grade_description = grade_descriptions[grade]

        # populate widgets
        self.set_title(name)
        self.set_subtitle(description)
        self.label_grade.set_text(grade)
        self.label_grade.get_style_context().add_class(f"grade-{grade}")
        self.set_tooltip_text(grade_description)

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
        InstallerDialog(self.window, self.config, self.installer).present()
