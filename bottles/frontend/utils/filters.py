# filters.py: File for providing common GtkFileFilters
#
# Copyright 2023 Bottles Contributors
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

from gi.repository import Gtk

def add_executable_filters(dialog):
    filter = Gtk.FileFilter()
    filter.set_name(_("Supported Executables"))
    # TODO: Investigate why `filter.add_mime_type(...)` does not show filter in all distributions.
    # Intended MIME types are:
    #   - `application-xms-dos-executable`
    #   - `application/x-msi`
    filter.add_pattern("*.exe")
    filter.add_pattern("*.msi")

    dialog.add_filter(filter)

def add_yaml_filters(dialog):
    filter = Gtk.FileFilter()
    filter.set_name("YAML")
    # TODO: Investigate why `filter.add_mime_type(...)` does not show filter in all distributions.
    # Intended MIME types are:
    #   - `application/yaml`
    filter.add_pattern("*.yml")
    filter.add_pattern("*.yaml")

    dialog.add_filter(filter)

def add_all_filters(dialog):
    filter = Gtk.FileFilter()
    filter.set_name(_("All Files"))
    filter.add_pattern("*")

    dialog.add_filter(filter)
