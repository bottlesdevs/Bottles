# localresources.py
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

from bottles.dialogs.filechooser import FileChooser  # pyright: reportMissingImports=false


@Gtk.Template(resource_path='/com/usebottles/bottles/local-resource-entry.ui')
class LocalResourceEntry(Adw.ActionRow):
    __gtype_name__ = 'LocalResourceEntry'

    # region Widgets
    btn_path = Gtk.Template.Child()

    # endregion

    def __init__(self, parent, resource, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.resource = resource

        self.set_title(resource)

        # connect signals
        self.btn_path.connect("clicked", self.__choose_path)

    def __choose_path(self, *args):
        """
        Open the file chooser dialog and set the path to the
        selected file
        """
        def set_path(_dialog, response, _file_dialog):
            _file = _file_dialog.get_file()
            if _file is None or response != -3:
                _dialog.destroy()
                return
            path = _file.get_path()
            self.parent.add_resource(self.resource, path)
            self.set_subtitle(path)
            _dialog.destroy()

        FileChooser(
            parent=self.parent.window,
            title=_("Select Resource FIle"),
            action=Gtk.FileChooserAction.OPEN,
            buttons=(_("Cancel"), _("Select")),
            callback=set_path
        )


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-local-resources.ui')
class LocalResourcesDialog(Adw.Window):
    __gtype_name__ = 'LocalResourcesDialog'
    __resources: dict = {}

    # region Widgets
    btn_save = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    group_resources = Gtk.Template.Child()

    # endregion

    def __init__(self, window, resources, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.resources = resources
        self.main_loop = GLib.MainLoop()

        self.__populate_resources_list()

        # connect signals
        self.btn_save.connect("clicked", self.__close)
        self.btn_cancel.connect("clicked", self.__close)

    def run(self):
        self.present()
        self.main_loop.run()

    def __close(self, *args):
        self.main_loop.quit()
        self.destroy()
        self.close()

    def __populate_resources_list(self):
        for resource in self.resources:
            _entry = LocalResourceEntry(self, resource)
            GLib.idle_add(self.group_resources.add, _entry)

    def get_resources(self):
        return self.__resources

    def add_resource(self, resource, path):
        self.__resources[resource] = path
        if len(self.resources) == len(self.__resources):
            self.btn_save.set_sensitive(True)
