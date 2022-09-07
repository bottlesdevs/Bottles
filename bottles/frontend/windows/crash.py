# crash.py
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

import os
import json
import contextlib
import webbrowser
import urllib.request
from urllib.parse import quote
from gi.repository import Gtk, Adw

from bottles.frontend.params import VERSION  # pyright: reportMissingImports=false


class SimilarReportEntry(Adw.ActionRow):
    def __init__(self, report: dict):
        super().__init__()

        self.set_title(report["title"])
        btn_report = Gtk.Button(label=_("Show report"))
        btn_report.add_css_class("flat")
        self.add_suffix(btn_report)

        btn_report.connect("clicked", self.__on_btn_report_clicked, report)

    @staticmethod
    def __on_btn_report_clicked(button, report):
        """
        This function opens the report in the default browser, it will
        use the active instance if there is one.
        """
        webbrowser.open(report["html_url"])


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-crash-report.ui')
class CrashReportDialog(Adw.Window):
    __gtype_name__ = 'CrashReportDialog'

    # region Widgets
    btn_send = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    label_notice = Gtk.Template.Child()
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
        self.btn_send.connect("clicked", self.__open_github, log)
        self.check_unlock_send.connect('toggled', self.__on_unlock_send)

        self.label_output.set_text(log)
        __similar_reports = self.__get_similar_issues(log)
        if len(__similar_reports) >= 5:
            '''
            This issue was reported 5 times, preventing the user from
            sending it again.
            '''
            prevent_text = _("""\
            This issue was reported 5 times and cannot be sent again.
            Report your feedback in one of the below existing reports.""")
            self.check_unlock_send.set_sensitive(False)
            self.btn_send.set_tooltip_text(prevent_text)
            self.label_notice.set_text(prevent_text)

        elif len(__similar_reports) > 0:
            '''
            If there are similar reports, show the box_related and
            append them to list_reports. Otherwise, make the btn_send
            sensitive, so the user can send the report.
            '''
            i = 0
            for issue in __similar_reports:
                self.list_reports.add(SimilarReportEntry(issue))
                i += 1
                if i == 5:
                    break
            self.box_related.set_visible(True)
        else:
            self.btn_send.set_sensitive(True)

    def __on_unlock_send(self, widget):
        """
        This function make the btn_send sensitive, so the user can send
        the new report.
        """
        self.btn_send.set_sensitive(widget.get_active())

    @staticmethod
    def __get_similarity(log: str, issue: dict) -> int:
        """
        This function returns the similarity between the log and the
        issue body.
        """
        log = log.lower()
        report = issue["body"]
        if report is None:
            return 0

        report = report.lower()

        log_words = log.split(" ")
        report_words = report.split(" ")

        log_words = [word for word in log_words if word != ""]
        report_words = [word for word in report_words if word != ""]

        log_words_set = set(log_words)
        report_words_set = set(report_words)

        return len(log_words_set.intersection(report_words_set))

    @staticmethod
    def __get_similar_issues(log):
        """
        This function will get the similar reports from the github
        api and return them as a list. It will return an empty list
        if there are no similar reports.
        """
        similar_issues = []
        api_url = "https://api.github.com/repos/bottlesdevs/Bottles/issues?filter=all&state=all"
        with contextlib.suppress(urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TypeError):
            with urllib.request.urlopen(api_url) as r:
                data = r.read().decode("utf-8")
                data = json.loads(data)

            for d in data:
                similarity = CrashReportDialog.__get_similarity(log, d)
                if similarity >= 18:
                    similar_issues.append(d)

        return similar_issues

    '''Run executable with args'''

    def __open_github(self, widget, log):
        """
        This function opens the page for creating a new issue on github,
        with the form filled in with the report details and log.
        """
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

        title = log.split('\n', 1)[0]
        title = title.split("File")[0]
        title = title.strip()[:40]
        title = f"%5BCrash%20report%5D+ {title}"

        template = f"This crash report was generated by Bottles.%0A%0A" \
                   "**Details**%0A" \
                   f"{details}%0A%0A" \
                   "**Log**%0A" \
                   "```python3%0A" \
                   f"{log}%0A" \
                   "```"
        issue_url = [
            "https://github.com/bottlesdevs/Bottles/issues/new",
            "?assignees=mirkobrombin",
            "&labels=crash",
            f"&title={title}",
            f"&body={template}"
        ]
        webbrowser.open("".join(issue_url))
        self.close()
