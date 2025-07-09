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

from gettext import gettext as _

from gi.repository import Gio, GObject, Gtk


def add_executable_filters(dialog):
    # TODO: Investigate why `filter.add_mime_type(...)` does not show filter in all distributions.
    # Intended MIME types are:
    #   - `application/x-ms-dos-executable`
    #   - `application/x-msi`
    __set_filter(dialog, _("Supported Executables"), ["*.exe", "*.msi"])


def add_yaml_filters(dialog):
    # TODO: Investigate why `filter.add_mime_type(...)` does not show filter in all distributions.
    # Intended MIME types are:
    #   - `application/yaml`
    __set_filter(dialog, "YAML", ["*.yaml", "*.yml"])


def add_all_filters(dialog):
    __set_filter(dialog, _("All Files"), ["*"])


def __set_filter(dialog: GObject.Object, name: str, patterns: list[str]):
    """Set dialog named file filter from list of extension patterns."""

    filter = Gtk.FileFilter()
    filter.set_name(name)
    for pattern in patterns:
        filter.add_pattern(pattern)

    if isinstance(dialog, Gtk.FileDialog):
        filters = dialog.get_filters() or Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter)
        dialog.set_filters(filters)
    elif isinstance(dialog, Gtk.FileChooserNative):
        dialog.add_filter(filter)
    else:
        raise TypeError
