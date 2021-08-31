# crash.py
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

import os
import json
import webbrowser
import urllib.request
from urllib.parse import quote
from gi.repository import Gtk, Handy

from ..params import VERSION

api_url = "https://api.github.com/repos/bottlesdevs/Bottles/issues?filter=all&state=all&labels=crash"


class SimilarReportEntry(Gtk.Box):
    def __init__(self, report: dict):
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )

        label_report = Gtk.Label(report["title"])
        btn_report = Gtk.Button(label=_("Show report"))

        self.pack_start(label_report, True, True, 0)
        self.pack_end(btn_report, False, False, 0)

        btn_report.connect("clicked", self.__on_btn_report_clicked, report)

        self.show_all()

    @staticmethod
    def __on_btn_report_clicked(button: Gtk.Button, report):
        '''
        This function opens the report in the default browser, it will
        use the active instance if there is one.
        '''
        webbrowser.open(report["url"])


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-crash-report.ui')
class CrashReportDialog(Handy.Window):
    __gtype_name__ = 'CrashReportDialog'

    # region Widgets
    btn_cancel = Gtk.Template.Child()
    btn_send = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    box_related = Gtk.Template.Child()
    check_unlock_send = Gtk.Template.Child()
    list_reports = Gtk.Template.Child()
    # endregion

    def __init__(self, window, log, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        if type(log) == list:
            log = "".join(log)

        # connect signals
        self.btn_cancel.connect('pressed', self.__close_window)
        self.btn_send.connect('pressed', self.__open_github, log)
        self.check_unlock_send.connect('toggled', self.__on_unlock_send)

        self.label_output.set_text(log)
        __similar_reports = self.__get_similar_issues(log)

        if len(__similar_reports) > 0:
            '''
            If there are similar reports, show the box_related and
            append them to list_reports. Otherwise, make the btn_send
            sensitive, so the user can send the report.
            '''
            self.box_related.set_visible(True)
            for issue in __similar_reports:
                self.list_reports.add(SimilarReportEntry(issue))
        else:
            self.btn_send.set_sensitive(True)

    def __on_unlock_send(self, widget):
        '''
        This function make the btn_send sensitive, so the user can send
        the new report.
        '''
        self.btn_send.set_sensitive(widget.get_active())

    @staticmethod
    def __get_similar_issues(log):
        '''
        This function will get the similar reports from the github
        api and return them as a list. It will return an empty list
        if there are no similar reports.
        '''
        similar_issues = []
        try:
            with urllib.request.urlopen(api_url) as r:
                data = r.read().decode("utf-8")
                data = json.loads(data)

            for d in data:
                if log.split('\n', 1)[0] in d["body"]:
                    similar_issues.append({
                        "title": d["title"],
                        "url": d["html_url"]
                    })
        except:
            pass

        return similar_issues

    def __close_window(self, widget=None):
        self.destroy()

    '''Run executable with args'''

    @staticmethod
    def __open_github(widget, log):
        '''
        This function opens the page for creating a new issue on github,
        with the form filled in with the report details and log.
        '''
        log = quote(log)
        details_list = {}

        if "FLATPAK_ID" in os.environ:
            details_list["package"] = "Flatpak"

        elif "APPDIR" in os.environ:
            details_list["package"] = "AppImage"

        elif "SNAP" in os.environ:
            details_list["package"] = "Snap"

        else:
            details_list["package"] = "Other"

        details_list["version"] = VERSION

        details = ""
        for d in details_list:
            details += f"* **{d}**: {details_list[d]}%0A"

        template = f"This crash report was generated by Bottles.%0A%0A"\
            "**Details**%0A"\
            f"{details}%0A%0A"\
            "**Log**%0A"\
            "```python3%0A"\
            f"{log}%0A"\
            "```"
        webbrowser.open(
            f"https://github.com/bottlesdevs/Bottles/issues/new?assignees=mirkobrombin&labels=crash&title=%5BCrash%20report%5D+&body={template}"
        )
