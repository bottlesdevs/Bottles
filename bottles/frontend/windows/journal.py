# journal.py
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

from datetime import datetime
from gettext import gettext

from gi.repository import Adw, Gtk, Pango

from bottles.backend.managers.journal import JournalManager, JournalSeverity


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-journal.ui")
class JournalDialog(Adw.Window):
    __gtype_name__ = "JournalDialog"

    # region Widgets
    tree_view = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    btn_all = Gtk.Template.Child()
    btn_critical = Gtk.Template.Child()
    btn_error = Gtk.Template.Child()
    btn_warning = Gtk.Template.Child()
    btn_info = Gtk.Template.Child()
    label_filter = Gtk.Template.Child()

    # endregion

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.journal = list(JournalManager.get(period="all").items())
        self.store = Gtk.ListStore(str, str, str, bool)
        self.current_severity = ""

        # connect signals
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.btn_all.connect("clicked", self.filter_results, "")
        self.btn_critical.connect(
            "clicked", self.filter_results, JournalSeverity.CRITICAL
        )
        self.btn_error.connect("clicked", self.filter_results, JournalSeverity.ERROR)
        self.btn_warning.connect(
            "clicked", self.filter_results, JournalSeverity.WARNING
        )
        self.btn_info.connect("clicked", self.filter_results, JournalSeverity.INFO)

        self.__setup_tree_view()
        self.populate_tree_view()

    def __setup_tree_view(self):
        self.tree_view.set_model(self.store)
        self.tree_view.set_search_column(2)

        for column in self.tree_view.get_columns():
            self.tree_view.remove_column(column)

        severity_renderer = Gtk.CellRendererText()
        severity_column = Gtk.TreeViewColumn(gettext("Severity"), severity_renderer)
        severity_column.set_cell_data_func(
            severity_renderer, self.__get_cell_data_func(0)
        )
        severity_column.set_resizable(True)
        severity_column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.tree_view.append_column(severity_column)

        timestamp_renderer = Gtk.CellRendererText()
        timestamp_column = Gtk.TreeViewColumn(gettext("Timestamp"), timestamp_renderer)
        timestamp_column.set_cell_data_func(
            timestamp_renderer, self.__get_cell_data_func(1)
        )
        timestamp_column.set_resizable(True)
        timestamp_column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.tree_view.append_column(timestamp_column)

        message_renderer = Gtk.CellRendererText()
        message_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)

        message_column = Gtk.TreeViewColumn(gettext("Message"), message_renderer)
        message_column.set_cell_data_func(
            message_renderer, self.__get_cell_data_func(2)
        )
        message_column.set_expand(True)
        message_column.set_resizable(True)
        message_column.set_sizing(Gtk.TreeViewColumnSizing.GROW_ONLY)
        message_column.set_min_width(260)
        self.tree_view.append_column(message_column)

    def populate_tree_view(self, query="", severity=None):
        self.store.clear()

        if severity is None:
            severity = self.current_severity

        colors = {
            JournalSeverity.CRITICAL: "#db1600",
            JournalSeverity.ERROR: "#db6600",
            JournalSeverity.WARNING: "#dba100",
            JournalSeverity.INFO: "#3283a8",
            JournalSeverity.CRASH: "#db1600",
        }

        last_date_label = None

        for _, value in self.journal:
            if query.lower() not in value["message"].lower():
                continue

            if severity not in ("", value["severity"]):
                continue

            timestamp = value.get("timestamp", "")
            try:
                timestamp_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                date_label = timestamp_dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                date_label = ""

            if date_label != last_date_label:
                self.store.append(["", date_label, "", True])
                last_date_label = date_label

            self.store.append(
                [
                    '<span foreground="{}"><b>{}</b></span>'.format(
                        colors.get(
                            value["severity"],
                            colors.get(JournalSeverity.INFO, "#3283a8"),
                        ),
                        value["severity"].capitalize(),
                    ),
                    timestamp,
                    value.get("message", ""),
                    False,
                ]
            )

    def on_search_changed(self, entry):
        self.populate_tree_view(entry.get_text())

    def filter_results(self, _, severity):
        self.current_severity = severity
        self.populate_tree_view(self.search_entry.get_text())

        severity_labels = {
            JournalSeverity.CRITICAL: gettext("Critical"),
            JournalSeverity.ERROR: gettext("Errors"),
            JournalSeverity.WARNING: gettext("Warnings"),
            JournalSeverity.INFO: gettext("Info"),
            JournalSeverity.CRASH: gettext("Crashes"),
        }

        label = severity_labels.get(severity, gettext("All messages"))
        self.label_filter.set_text(label)

    def __get_cell_data_func(self, column_index):
        def _cell_data_func(column, renderer, model, iter_, _data=None):
            self.__populate_cell(renderer, model, iter_, column_index)

        return _cell_data_func

    def __populate_cell(self, renderer, model, iter_, column_index):
        is_group = model.get_value(iter_, 3)

        renderer.set_property("text", None)

        if is_group:
            if column_index == 1:
                renderer.set_property("markup", f"<b>{model.get_value(iter_, 1)}</b>")
            else:
                renderer.set_property("text", "")
            return

        if column_index == 0:
            renderer.set_property("markup", model.get_value(iter_, 0))
        elif column_index == 1:
            renderer.set_property("text", model.get_value(iter_, 1))
        elif column_index == 2:
            renderer.set_property("text", model.get_value(iter_, 2))
