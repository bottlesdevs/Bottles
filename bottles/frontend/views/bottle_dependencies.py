# bottle_installers.py
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

import time
from gettext import gettext as _, ngettext
from typing import Optional

from gi.repository import Adw, GLib, Gtk

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import EventManager, Events
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.common import open_doc_url
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.widgets.dependency import DependencyEntry
from bottles.frontend.windows.dependency_install import DependencyInstallDialog

logging = Logger()


@Gtk.Template(resource_path="/com/usebottles/bottles/details-dependencies.ui")
class DependenciesView(Adw.Bin):
    __gtype_name__ = "DetailsDependencies"
    __registry = []

    # region Widgets
    list_dependencies = Gtk.Template.Child()
    btn_report = Gtk.Template.Child()
    btn_help = Gtk.Template.Child()
    btn_select_all = Gtk.Template.Child()
    btn_install_selected = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    ev_controller = Gtk.EventControllerKey.new()
    spinner_loading = Gtk.Template.Child()
    stack = Gtk.Template.Child()

    # endregion

    def __init__(self, details, config: BottleConfig, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = details.window
        self.manager = details.window.manager
        self.config = config
        self.queue = details.queue

        self.ev_controller.connect("key-released", self.__search_dependencies)
        # also re-filter on text changes (e.g. clicking the clear icon, which
        # does not emit a key event) so the list resets correctly
        self.entry_search.connect("search-changed", self.__search_dependencies)

        self.entry_search.add_controller(self.ev_controller)
        self.search_bar.set_key_capture_widget(self.window)

        self.btn_report.connect(
            "clicked", open_doc_url, "contribute/missing-dependencies"
        )
        self.btn_help.connect("clicked", open_doc_url, "bottles/dependencies")
        self.btn_select_all.connect("clicked", self.__toggle_all)
        self.btn_install_selected.connect("clicked", self.__install_selected)
        self.list_dependencies.connect("notify::sensitive", self.__selection_changed)

        if not self.manager.utils_conn.status:
            self.stack.set_visible_child_name("page_offline")

        self.spinner_loading.start()

    def __search_dependencies(self, *_args):
        """
        This function search in the list of dependencies the
        text written in the search entry.
        """
        terms = self.entry_search.get_text()
        self.list_dependencies.set_filter_func(self.__filter_dependencies, terms)

    @staticmethod
    def __filter_dependencies(row, terms=None):
        text = row.get_title().lower() + row.get_subtitle().lower()
        if terms.lower() in text:
            return True
        return False

    def empty_list(self):
        for r in self.__registry:
            if r.get_parent() is not None:
                r.get_parent().remove(r)
        self.__registry = []
        self.btn_select_all.set_visible(False)
        self.btn_select_all.set_sensitive(False)
        self.btn_install_selected.set_visible(False)
        self.btn_install_selected.set_sensitive(False)

    def __selection_changed(self, *_args):
        selectable = [
            entry for entry in self.__registry if entry.check_select.get_visible()
        ]
        selected = [entry for entry in selectable if entry.check_select.get_active()]
        all_selected = bool(selectable) and len(selected) == len(selectable)
        list_sensitive = self.list_dependencies.get_sensitive()
        self.btn_select_all.set_visible(bool(selectable))
        self.btn_select_all.set_sensitive(bool(selectable) and list_sensitive)
        self.btn_select_all.set_label(
            _("Clear Selection") if all_selected else _("Select All")
        )
        self.btn_install_selected.set_visible(bool(selectable))
        self.btn_install_selected.set_sensitive(bool(selected) and list_sensitive)

    def __toggle_all(self, *_args):
        selectable = [
            entry for entry in self.__registry if entry.check_select.get_visible()
        ]
        if not selectable:
            return

        active = not all(entry.check_select.get_active() for entry in selectable)
        for entry in selectable:
            entry.check_select.set_active(active)

    def __install_dependencies(self, entries, dialog):
        installed = []
        failed = []

        for entry in entries:
            dependency = entry.dependency
            name = dependency[0]
            if name in self.config.Installed_Dependencies:
                installed.append(name)
                continue

            dialog.add_step(_('Installing "{0}"...').format(name))
            try:
                result = self.manager.dependency_manager.install(
                    config=self.config,
                    dependency=dependency,
                    progress_cb=dialog.add_step,
                    progress_progress_cb=dialog.update_progress,
                )
            except Exception as exception:
                logging.error(
                    f"Failed to install dependency [{name}]: {exception}", jn=False
                )
                failed.append(name)
                continue
            if result is not None and result.status:
                installed.append(name)
            else:
                failed.append(name)

        return Result(
            status=not failed,
            data={"installed": installed, "failed": failed},
        )

    def __install_selected(self, *_args):
        entries = [
            entry
            for entry in self.__registry
            if entry.check_select.get_visible() and entry.check_select.get_active()
        ]
        if not entries:
            return

        count = len(entries)
        title = ngettext("{0} dependency", "{0} dependencies", count).format(count)
        dialog = DependencyInstallDialog(self.window, title)
        dialog.present()
        self.queue.add_task()
        self.list_dependencies.set_sensitive(False)
        self.btn_select_all.set_sensitive(False)
        self.btn_install_selected.set_sensitive(False)

        def complete(result, error=False):
            self.queue.end_task()
            self.list_dependencies.set_sensitive(True)

            if result is None:
                message = _("Dependency installation failed.")
                success = False
            else:
                installed = len(result.data["installed"])
                failed = len(result.data["failed"])
                success = result.status
                if installed and self.config.Parameters.versioning_automatic:
                    self.window.page_details.view_versioning.update()
                if failed:
                    message = _("{0} installed, {1} failed.").format(installed, failed)
                else:
                    message = ngettext(
                        "{0} dependency installed.",
                        "{0} dependencies installed.",
                        installed,
                    ).format(installed)

            dialog.finish(success, message)
            self.window.show_toast(message)
            self.update(config=self.config)

        RunAsync(
            task_func=self.__install_dependencies,
            callback=complete,
            entries=entries,
            dialog=dialog,
        )

    def update(self, _widget=False, config: Optional[BottleConfig] = None):
        """
        This function update the dependencies list with the
        supported by the manager.
        """
        if config is None:
            config = BottleConfig()
        self.config = config
        self.btn_select_all.set_sensitive(False)
        self.btn_install_selected.set_sensitive(False)

        self.stack.set_visible_child_name("page_loading")

        def new_dependency(dependency, plain=False):
            entry = DependencyEntry(
                window=self.window,
                config=self.config,
                dependency=dependency,
                plain=plain,
            )
            self.__registry.append(entry)
            self.list_dependencies.append(entry)
            entry.check_select.connect("toggled", self.__selection_changed)
            entry.check_select.connect("notify::visible", self.__selection_changed)
            self.__selection_changed()

        @GtkUtils.run_in_main_loop
        def callback(_result, _error=False):
            page = (
                "page_deps"
                if self.manager.supported_dependencies or self.manager.utils_conn.status
                else "page_offline"
            )
            self.stack.set_visible_child_name(page)

        def process_dependencies():
            time.sleep(0.3)  # workaround for freezing bug on bottle load
            EventManager.wait(Events.DependenciesOrganizing)
            dependencies = self.manager.supported_dependencies

            GLib.idle_add(self.empty_list)

            if len(dependencies.keys()) > 0:
                for dep in dependencies.items():
                    if dep[0] in self.config.Installed_Dependencies:
                        continue  # Do not list already installed dependencies

                    GLib.idle_add(new_dependency, dep)

            if len(self.config.Installed_Dependencies) > 0:
                for dep in self.config.Installed_Dependencies:
                    if dep in dependencies:
                        dep = (dep, dependencies[dep])
                        GLib.idle_add(new_dependency, dep)

        RunAsync(process_dependencies, callback=callback)
