# journal.py
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

from bottles.backend.managers.journal import JournalManager, JournalSeverity


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-journal.ui')
class JournalDialog(Adw.Window):
    __gtype_name__ = 'JournalDialog'

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

        self.journal = JournalManager.get().items()
        self.store = Gtk.ListStore(str, str, str)

        # connect signals
        self.search_entry.connect('search-changed', self.on_search_changed)
        self.btn_all.connect('clicked', self.filter_results, "")
        self.btn_critical.connect('clicked', self.filter_results, JournalSeverity.CRITICAL)
        self.btn_error.connect('clicked', self.filter_results, JournalSeverity.ERROR)
        self.btn_warning.connect('clicked', self.filter_results, JournalSeverity.WARNING)
        self.btn_info.connect('clicked', self.filter_results, JournalSeverity.INFO)

        self.populate_tree_view()

    def populate_tree_view(self, query="", severity=""):
        self.store.clear()

        colors = {
            JournalSeverity.CRITICAL: '#db1600',
            JournalSeverity.ERROR: '#db6600',
            JournalSeverity.WARNING: '#dba100',
            JournalSeverity.INFO: '#3283a8',
            JournalSeverity.CRASH: '#db1600',
        }

        for _, value in self.journal:
            if query.lower() in value['message'].lower() \
                    and (severity == "" or severity == value['severity']):
                self.store.append([
                    '<span foreground="{}"><b>{}</b></span>'.format(
                        colors[value['severity']], value['severity'].capitalize()),
                    value['timestamp'],
                    value['message']
                ])

        self.tree_view.set_model(self.store)
        self.tree_view.set_search_column(1)

        self.tree_view.append_column(Gtk.TreeViewColumn('Severity', Gtk.CellRendererText(), markup=0))
        self.tree_view.append_column(Gtk.TreeViewColumn('Timestamp', Gtk.CellRendererText(), text=1))
        self.tree_view.append_column(Gtk.TreeViewColumn('Message', Gtk.CellRendererText(), text=2))

    def on_search_changed(self, entry):
        self.populate_tree_view(entry.get_text())

    def filter_results(self, _, severity):
        self.populate_tree_view(self.search_entry.get_text(), severity)
        label = severity if severity != "" else "all"
        self.label_filter.set_text(label.capitalize())
