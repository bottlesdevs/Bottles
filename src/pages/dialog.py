# dialog.py
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

from urllib.parse import quote
import urllib.request
import webbrowser
import json
import os
import gi

gi.require_version('Handy', '1')
from gi.repository import Gtk, Handy, Pango

from ..params import VERSION

class BottlesMessageDialog(Gtk.MessageDialog):

    def __init__(self,
                 parent,
                 title=_("Warning"),
                 message=_("An error has occurred."),
                 log=False):

        Gtk.MessageDialog.__init__(self,
                                   parent=parent,
                                   flags=Gtk.DialogFlags.USE_HEADER_BAR,
                                   type=Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   message_format=message)

        '''Display log as output if defined'''
        if log:
            message_scroll = Gtk.ScrolledWindow()
            message_scroll.set_hexpand(True)
            message_scroll.set_vexpand(True)

            message_view = Gtk.TextView()
            message_buffer = message_view.get_buffer()
            message_buffer.set_text(log)
            message_scroll.add(message_view)

        content = self.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(20)

        if log:
            box.add(message_scroll)

        content.add(box)
        self.show_all()


class BottlesDialog(Gtk.Dialog):

    def __init__(self,
                 parent,
                 title=_("Warning"),
                 message=False,
                 log=False):

        Gtk.Dialog.__init__(self,
                            title=title,
                            parent=parent,
                            flags=Gtk.DialogFlags.USE_HEADER_BAR)

        '''Display log as output if defined'''
        if log:
            self.resize(600, 700)
            color = "#3e0622"
            if parent is not None and parent.settings.get_boolean("dark-theme"):
                color = "#d4036d"
            message_scroll = Gtk.ScrolledWindow()
            message_scroll.set_hexpand(True)
            message_scroll.set_vexpand(True)

            message_view = Gtk.TextView()
            message_buffer = message_view.get_buffer()
            buffer_iter = message_buffer.get_end_iter()
            message_buffer.insert_markup(
                buffer_iter, "<span foreground='%s'>%s</span>" % (color, log), -1)
            message_scroll.add(message_view)
        else:
            message_label = Gtk.Label(label=message)
            message_label.wrap_width = 500
            message_label.wrap_mode = Pango.WrapMode.WORD_CHAR

        content = self.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(20)

        if log:
            box.add(message_scroll)
        if message:
            box.add(message_label)

        content.add(box)
        self.show_all()


@Gtk.Template(resource_path='/com/usebottles/bottles/about.ui')
class BottlesAboutDialog(Gtk.AboutDialog):
    __gtype_name__ = 'BottlesAboutDialog'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class BottlesSimilarReportEntry(Gtk.Box):
    def __init__(self, report: dict):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.report = report

        label_report = Gtk.Label(report["title"])
        btn_report = Gtk.Button(label=_("Show report"))

        self.pack_start(label_report, True, True, 0)
        self.pack_end(btn_report, False, False, 0)

        btn_report.connect("clicked", self.__on_btn_report_clicked)

        self.show_all()
    
    def __on_btn_report_clicked(self, button: Gtk.Button):
        webbrowser.open(self.report["url"])

@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-crash-report.ui')
class BottlesCrashReport(Handy.Window):
    __gtype_name__ = 'BottlesCrashReport'

    '''Get widgets from template'''
    btn_cancel = Gtk.Template.Child()
    btn_send = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    box_related = Gtk.Template.Child()
    check_unlock_send = Gtk.Template.Child()
    list_reports = Gtk.Template.Child()

    def __init__(self, window, log, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        '''Signal connections'''
        self.btn_cancel.connect('pressed', self.__close_window)
        self.btn_send.connect('pressed', self.__open_github)

        if type(log) == list:
            log = "".join(log)

        self.log = log
        self.label_output.set_text(log)

        if len(self.__get_similar_issues()) > 0:
            self.box_related.set_visible(True)
            for issue in self.__get_similar_issues():
                self.list_reports.add(BottlesSimilarReportEntry(issue))
        else:
            self.btn_send.set_sensitive(True)

        self.check_unlock_send.connect('toggled', self.__on_unlock_send)
        
    def __on_unlock_send(self, widget):
        self.btn_send.set_sensitive(widget.get_active())

    def __get_similar_issues(self):
        similar_issues = []
        url = "https://api.github.com/repos/bottlesdevs/Bottles/issues?filter=all&state=all&labels=crash"
        try:
            with urllib.request.urlopen(url) as r:
                data = r.read().decode("utf-8")
                data = json.loads(data)

            for d in data:
                if self.log.split('\n', 1)[0] in d["body"]:
                    similar_issues.append({
                        "title": d["title"],
                        "url": d["html_url"]
                    })
        except:
            pass

        return similar_issues

    '''Destroy the window'''

    def __close_window(self, widget=None):
        self.destroy()

    '''Run executable with args'''

    def __open_github(self, widget):
        log = quote(self.log)
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
            f"https://github.com/bottlesdevs/Bottles/issues/new?assignees=mirkobrombin&labels=crash&title=%5BCrash%20report%5D+&body={template}")
