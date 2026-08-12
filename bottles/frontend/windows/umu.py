# umu.py
#
# Copyright 2026 mirkobrombin <brombin94@gmail.com>
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

import shlex
from concurrent.futures import ThreadPoolExecutor
from gettext import gettext as _, ngettext
from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk

from bottles.backend.logger import Logger
from bottles.backend.managers.library import LibraryManager
from bottles.backend.umu import (
    DEFAULT_PROTON_VALUE,
    RESERVED_ENVIRONMENT_KEYS,
    UMU_STORE_IDS,
    UmuDatabaseEntry,
    UmuDependencyInstaller,
    UmuPrefix,
    UmuRepositoryError,
)
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.sh import ShUtils
from bottles.frontend.utils.umu import get_umu_store_title
from bottles.frontend.windows.dependency_install import DependencyInstallDialog

logging = Logger()

STORE_IDS = UMU_STORE_IDS
DEPENDENCY_TOOL_IDS = ("bottles", "winetricks")


def _store_labels():
    return tuple(
        _("None") if store == "none" else get_umu_store_title(store)
        for store in STORE_IDS
    )


def _store_title(store):
    return _store_labels()[STORE_IDS.index(store)]


def _dependency_tool_labels():
    return (_("Bottles Dependencies"), "Winetricks")


def _selected_id(combo, values):
    position = combo.get_selected()
    if position >= len(values):
        return values[0]
    return values[position]


def _select_id(combo, values, value):
    try:
        combo.set_selected(values.index(value))
    except ValueError:
        combo.set_selected(0)


def _windows_file_filters(title, patterns):
    filters = Gio.ListStore.new(Gtk.FileFilter)
    windows_filter = Gtk.FileFilter()
    windows_filter.set_name(title)
    for pattern in patterns:
        windows_filter.add_pattern(pattern)
    filters.append(windows_filter)
    return filters, windows_filter


def _validate_windows_file(path, allowed_suffixes):
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise ValueError(_("The selected file does not exist."))

    suffix = candidate.suffix.casefold()
    if suffix not in allowed_suffixes:
        raise ValueError(_("The selected file type is not supported."))

    try:
        with candidate.open("rb") as stream:
            header = stream.read(8)
    except OSError as error:
        raise ValueError(_("The selected file cannot be read.")) from error

    signatures = {
        ".exe": b"MZ",
        ".msi": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
    }
    if not header.startswith(signatures[suffix]):
        raise ValueError(_("The selected file is not a valid Windows program."))
    return candidate.resolve()


def _proton_title(catalog, value):
    for choice in catalog.list_choices(include_unstable=True):
        if choice.value == value or choice.component_name == value:
            return choice.title
    return Path(value).name or value


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-umu-proton.ui")
class UmuProtonDialog(Adw.Dialog):
    __gtype_name__ = "UmuProtonDialog"

    btn_cancel = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    stack_results = Gtk.Template.Child()
    group_choices = Gtk.Template.Child()

    def __init__(self, window, selected, callback, **kwargs):
        super().__init__(**kwargs)
        self.window = window
        self.selected = selected
        self.callback = callback
        self.catalog = window.manager.umu_proton_catalog
        self.rows = []

        self.btn_cancel.connect("clicked", lambda *_args: self.close())
        self.entry_search.connect("search-changed", self.__populate)
        self.__populate()

    def __populate(self, *_args):
        for row in self.rows:
            self.group_choices.remove(row)
        self.rows = []

        choices = self.catalog.list_choices(
            self.entry_search.get_text(),
            include_unstable=self.window.settings.get_boolean("release-candidate"),
        )
        self.stack_results.set_visible_child_name("choices" if choices else "empty")
        for choice in choices:
            row = self.__build_row(choice)
            self.group_choices.add(row)
            self.rows.append(row)

    def __build_row(self, choice):
        subtitles = {
            "auto": _("Downloaded and updated automatically by UMU."),
            "bottles": (
                _("Installed and managed by Bottles.")
                if choice.installed
                else _("Available from Bottles Components.")
            ),
            "steam": _("Discovered in Steam."),
        }
        subtitle = subtitles[choice.source]
        if choice.key == "auto:protosoda":
            subtitle = _(
                "Recommended for Bottles and managed through Bottles Components."
            )
        row = Adw.ActionRow(
            title=choice.title,
            subtitle=subtitle,
            use_markup=False,
        )
        row.add_prefix(Gtk.Image(icon_name="input-gaming-symbolic"))

        source = Gtk.Label(
            label={
                "auto": "UMU",
                "bottles": _("Bottles"),
                "steam": "Steam",
            }[choice.source],
            valign=Gtk.Align.CENTER,
        )
        source.add_css_class("tag")
        source.add_css_class("caption")
        row.add_suffix(source)

        if choice.value is not None:
            selected = (
                choice.value == self.selected or choice.component_name == self.selected
            )
            row.set_activatable(True)
            row.connect("activated", self.__select, choice)
            row.add_suffix(
                Gtk.Image(
                    icon_name=(
                        "object-select-symbolic" if selected else "go-next-symbolic"
                    )
                )
            )
        else:
            download = Gtk.Button(
                icon_name="folder-download-symbolic",
                tooltip_text=_("Install Proton"),
                valign=Gtk.Align.CENTER,
                sensitive=choice.downloadable,
            )
            download.add_css_class("flat")
            download.connect("clicked", self.__install, choice, row)
            row.add_suffix(download)
            if not choice.downloadable:
                row.set_subtitle(_("Not available while Bottles is offline."))
        return row

    def __select(self, _row, choice):
        try:
            value = self.catalog.validate_selection(choice.value)
        except ValueError as error:
            self.window.show_toast(str(error))
            self.__populate()
            return
        self.callback(value, choice.title)
        self.close()

    def __install(self, button, choice, row):
        button.set_sensitive(False)
        self.btn_cancel.set_sensitive(False)
        self.entry_search.set_sensitive(False)
        self.set_can_close(False)
        row.set_subtitle(_("Installing Proton..."))
        spinner = Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER)
        row.add_suffix(spinner)

        def complete(result, error=False):
            spinner.set_spinning(False)
            spinner.set_visible(False)
            if error or not result or not result.ok:
                button.set_sensitive(True)
                self.btn_cancel.set_sensitive(True)
                self.entry_search.set_sensitive(True)
                self.set_can_close(True)
                row.set_subtitle(
                    (result.message if result else "")
                    or _("Proton installation failed.")
                )
                return
            installed = result.data
            self.callback(installed.value, installed.title)
            self.set_can_close(True)
            self.close()

        RunAsync(
            self.catalog.install,
            callback=complete,
            component_name=choice.component_name,
        )


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-umu-dependencies.ui")
class UmuDependencyDialog(Adw.Dialog):
    __gtype_name__ = "UmuDependencyDialog"

    btn_cancel = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_retry = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    spinner = Gtk.Template.Child()
    stack_results = Gtk.Template.Child()
    list_dependencies = Gtk.Template.Child()
    status_empty = Gtk.Template.Child()

    def __init__(self, window, game, callback, **kwargs):
        super().__init__(**kwargs)
        self.window = window
        self.game = game
        self.callback = callback
        self.rows = []

        self.btn_cancel.connect("clicked", lambda *_args: self.close())
        self.btn_install.connect("clicked", self.__install)
        self.btn_retry.connect("clicked", self.__load_dependencies)
        self.entry_search.connect("search-changed", self.__search)
        self.list_dependencies.set_filter_func(self.__filter)
        self.__load_dependencies()

    def __load_dependencies(self, *_args):
        for row in self.rows:
            self.list_dependencies.remove(row)
        self.rows = []
        self.btn_install.set_sensitive(False)
        self.spinner.start()
        self.stack_results.set_visible_child_name("loading")
        RunAsync(self.__load, callback=self.__loaded)

    def __load(self):
        executor = self.window.manager.get_umu_executor(for_launch=False)
        if executor is None:
            return []
        checker = UmuDependencyInstaller(
            self.window.manager,
            self.window.manager.umu_repository,
            executor,
        )
        installed = self.game.extra.get("installed_dependencies", [])
        available = [
            (name, metadata)
            for name, metadata in self.window.manager.supported_dependencies.items()
            if name not in installed
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            compatibility = pool.map(
                lambda dependency: checker.is_compatible(dependency[0], installed),
                available,
            )
            return [
                dependency
                for dependency, compatible in zip(available, compatibility)
                if compatible
            ]

    def __loaded(self, dependencies, error=False):
        self.spinner.stop()
        if error:
            self.stack_results.set_visible_child_name("error")
            return
        if not dependencies:
            installed = self.game.extra.get("installed_dependencies", [])
            if installed:
                self.status_empty.set_title(_("No More Dependencies"))
                self.status_empty.set_description(
                    _("All compatible Bottles dependencies are already installed.")
                )
            else:
                self.status_empty.set_title(_("No Compatible Dependencies"))
                self.status_empty.set_description(
                    _("Use Winetricks if the dependency you need is not listed.")
                )
            self.stack_results.set_visible_child_name("empty")
            return
        for name, metadata in dependencies:
            row = Adw.ActionRow(
                title=name,
                subtitle=metadata.get("Description", ""),
                use_markup=False,
            )
            check = Gtk.CheckButton(
                valign=Gtk.Align.CENTER,
            )
            check.connect("toggled", self.__selection_changed)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            category = Gtk.Label(
                label=metadata.get("Category", _("Other")),
                valign=Gtk.Align.CENTER,
            )
            category.add_css_class("tag")
            category.add_css_class("caption")
            row.add_suffix(category)
            row._umu_name = name
            row._umu_check = check
            self.list_dependencies.append(row)
            self.rows.append(row)
        self.stack_results.set_visible_child_name("results")
        self.__selection_changed()

    def __filter(self, row):
        query = self.entry_search.get_text().strip().casefold()
        if not query:
            return True
        return query in f"{row.get_title()} {row.get_subtitle()}".casefold()

    def __search(self, *_args):
        self.list_dependencies.invalidate_filter()
        visible = any(self.__filter(row) for row in self.rows)
        if not visible and self.rows:
            self.status_empty.set_title(_("No Matching Dependencies"))
            self.status_empty.set_description(_("Try a different search."))
        self.stack_results.set_visible_child_name("results" if visible else "empty")

    def __selection_changed(self, *_args):
        selected = any(row._umu_check.get_active() for row in self.rows)
        self.btn_install.set_sensitive(selected)

    def __install(self, *_args):
        names = tuple(
            row._umu_name for row in self.rows if row._umu_check.get_active()
        )
        if not names:
            return

        title = ngettext("{0} dependency", "{0} dependencies", len(names)).format(
            len(names)
        )
        dialog = DependencyInstallDialog(self.window, title)
        self.close()
        dialog.present()

        def install():
            current = self.window.manager.umu_repository.load(self.game.id)
            current = self.window.manager.umu_repository.update(
                current,
                extra={**current.extra, "dependency_tool": "bottles"},
            )
            return self.window.manager.install_umu_dependencies(
                current,
                names,
                progress_cb=dialog.add_step,
                progress_progress_cb=dialog.update_progress,
            )

        def complete(result, error=False):
            success = not error and result is not None and result.status
            if result is not None and result.data is not None:
                self.callback(result.data)
            if success:
                message = ngettext(
                    "{0} dependency installed.",
                    "{0} dependencies installed.",
                    len(names),
                ).format(len(names))
            else:
                message = (
                    result.message if result is not None else ""
                ) or _("Dependency installation failed.")
            dialog.finish(success, message)
            self.window.show_toast(message)

        RunAsync(install, callback=complete)


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-umu-arguments.ui")
class UmuArgumentsDialog(Adw.Dialog):
    __gtype_name__ = "UmuArgumentsDialog"

    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    entry_arguments = Gtk.Template.Child()

    def __init__(self, window, arguments, callback, **kwargs):
        super().__init__(**kwargs)
        self.window = window
        self.callback = callback
        self.entry_arguments.set_text(shlex.join(arguments))
        self.btn_cancel.connect("clicked", lambda *_args: self.close())
        self.btn_save.connect("clicked", self.__save)
        self.entry_arguments.connect("activate", self.__save)

    def __save(self, *_args):
        try:
            arguments = tuple(shlex.split(self.entry_arguments.get_text()))
        except ValueError as error:
            self.window.show_toast(str(error))
            return
        self.callback(arguments)
        self.close()


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-umu-environment.ui")
class UmuEnvironmentDialog(Adw.Dialog):
    __gtype_name__ = "UmuEnvironmentDialog"

    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    entry_new_variable = Gtk.Template.Child()
    btn_add_variable = Gtk.Template.Child()
    group_variables = Gtk.Template.Child()

    def __init__(self, window, environment, callback, **kwargs):
        super().__init__(**kwargs)
        self.window = window
        self.callback = callback
        self.rows = {}

        for name, value in sorted(environment.items()):
            self.__add_row(name, value)
        self.__update_empty_state()

        self.btn_cancel.connect("clicked", lambda *_args: self.close())
        self.btn_save.connect("clicked", self.__save)
        self.btn_add_variable.connect("clicked", self.__add_variable)
        self.entry_new_variable.connect("changed", self.__validate_new_variable)
        self.entry_new_variable.connect("activate", self.__add_variable)

    def __add_row(self, name, value):
        row = Adw.EntryRow(title=name, show_apply_button=False)
        row.set_text(value)
        remove = Gtk.Button(
            icon_name="user-trash-symbolic",
            tooltip_text=_("Remove Variable"),
            valign=Gtk.Align.CENTER,
        )
        remove.add_css_class("flat")
        remove.connect("clicked", self.__remove_variable, name)
        row.add_suffix(remove)
        self.group_variables.add(row)
        self.rows[name] = row

    def __remove_variable(self, _button, name):
        row = self.rows.pop(name)
        self.group_variables.remove(row)
        self.__update_empty_state()

    def __validate_new_variable(self, *_args):
        text = self.entry_new_variable.get_text()
        name, separator, _value = text.partition("=")
        valid = bool(
            separator
            and ShUtils.is_name(name)
            and name not in RESERVED_ENVIRONMENT_KEYS
        )
        self.btn_add_variable.set_sensitive(valid)
        if text and not valid:
            self.entry_new_variable.add_css_class("error")
        else:
            self.entry_new_variable.remove_css_class("error")

    def __add_variable(self, *_args):
        if not self.btn_add_variable.get_sensitive():
            return
        name, value = ShUtils.split_assignment(
            self.entry_new_variable.get_text()
        )
        if name in self.rows:
            self.rows[name].set_text(value)
        else:
            self.__add_row(name, value)
        self.entry_new_variable.set_text("")
        self.__update_empty_state()

    def __update_empty_state(self):
        self.group_variables.set_description(
            None if self.rows else _("No custom variables are defined.")
        )

    def __save(self, *_args):
        environment = {
            name: row.get_text() for name, row in self.rows.items()
        }
        self.callback(environment)
        self.close()


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-umu-search.ui")
class UmuSearchDialog(Adw.Dialog):
    __gtype_name__ = "UmuSearchDialog"

    btn_cancel = Gtk.Template.Child()
    btn_empty_custom = Gtk.Template.Child()
    btn_retry = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    group_results = Gtk.Template.Child()
    list_results = Gtk.Template.Child()
    row_existing = Gtk.Template.Child()
    row_install = Gtk.Template.Child()
    spinner = Gtk.Template.Child()
    stack_pages = Gtk.Template.Child()
    stack_results = Gtk.Template.Child()

    def __init__(self, window, detected_prefix=None, **kwargs):
        super().__init__(**kwargs)
        self.window = window
        self.database = window.manager.umu_database
        self.detected_prefix = detected_prefix
        self.rows = []

        self.btn_cancel.connect("clicked", lambda *_args: self.close())
        self.btn_empty_custom.connect(
            "clicked",
            lambda *_args: self.stack_pages.set_visible_child_name("custom"),
        )
        self.btn_retry.connect("clicked", lambda *_args: self.__load(refresh=True))
        self.entry_search.connect("search-changed", self.__search)
        self.row_install.connect("activated", self.__custom, "install")
        self.row_existing.connect(
            "activated",
            self.__custom,
            "detected" if detected_prefix else "import",
        )
        if detected_prefix:
            self.row_install.set_visible(False)
            self.row_existing.set_title(_("Complete Detected Prefix"))
            self.row_existing.set_subtitle(
                _("Select the installed executable and finish its UMU identity.")
            )
        self.__load()

    def __load(self, refresh=False):
        self.entry_search.set_sensitive(False)
        self.stack_results.set_visible_child_name("loading")
        self.spinner.start()

        def loaded(entries, error=False):
            self.spinner.stop()
            if error or not entries:
                self.group_results.set_visible(True)
                self.stack_results.set_visible_child_name("error")
                return
            self.entry_search.set_sensitive(True)
            self.entry_search.grab_focus()
            self.__search()

        RunAsync(self.database.get_entries, callback=loaded, refresh=refresh)

    def __search(self, *_args):
        query = self.entry_search.get_text().strip()
        for row in self.rows:
            self.list_results.remove(row)
        self.rows = []
        if not query:
            self.group_results.set_visible(False)
            return

        matches = self.database.search(query)
        self.group_results.set_visible(True)
        self.stack_results.set_visible_child_name("results" if matches else "empty")
        for entry in matches:
            row = self.__build_row(entry)
            self.list_results.append(row)
            self.rows.append(row)

    def __build_row(self, entry):
        subtitle = _store_title(entry.store)
        if entry.notes:
            subtitle = _("{0}\n{1}").format(subtitle, entry.notes)
        row = Adw.ActionRow(
            title=entry.title,
            subtitle=subtitle,
            activatable=True,
            use_markup=False,
        )
        row.add_prefix(Gtk.Image(icon_name="input-gaming-symbolic"))
        row.connect("activated", self.__select, entry)
        return row

    def __select(self, _row, entry):
        self.close()
        if self.detected_prefix:
            UmuAddGameDialog(
                self.window,
                mode="detected",
                detected_prefix=self.detected_prefix,
                database_entry=entry,
            ).present(self.window)
            return
        UmuInstallDialog(self.window, entry).present(self.window)

    def __custom(self, _row, mode):
        self.close()
        if mode == "install":
            UmuInstallDialog(self.window).present(self.window)
            return
        UmuAddGameDialog(
            self.window,
            mode=mode,
            detected_prefix=self.detected_prefix,
        ).present(self.window)


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-umu-install.ui")
class UmuInstallDialog(Adw.Dialog):
    __gtype_name__ = "UmuInstallDialog"

    btn_back = Gtk.Template.Child()
    btn_next = Gtk.Template.Child()
    btn_installer = Gtk.Template.Child()
    btn_executable = Gtk.Template.Child()
    btn_done = Gtk.Template.Child()
    btn_retry = Gtk.Template.Child()
    window_title = Gtk.Template.Child()
    stack = Gtk.Template.Child()
    status_intro = Gtk.Template.Child()
    status_complete = Gtk.Template.Child()
    status_error = Gtk.Template.Child()
    row_identity = Gtk.Template.Child()
    row_store = Gtk.Template.Child()
    row_setup_identity = Gtk.Template.Child()
    row_setup_store = Gtk.Template.Child()
    page_files = Gtk.Template.Child()
    combo_source = Gtk.Template.Child()
    source_modes = Gtk.Template.Child()
    row_installer = Gtk.Template.Child()
    row_installer_validation = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    row_proton = Gtk.Template.Child()
    label_proton = Gtk.Template.Child()
    label_install_title = Gtk.Template.Child()
    label_install_description = Gtk.Template.Child()
    progress_install = Gtk.Template.Child()
    spinner_prepare = Gtk.Template.Child()
    spinner_run = Gtk.Template.Child()
    spinner_finish = Gtk.Template.Child()
    check_prepare = Gtk.Template.Child()
    check_run = Gtk.Template.Child()
    check_finish = Gtk.Template.Child()
    row_executable = Gtk.Template.Child()
    row_executable_validation = Gtk.Template.Child()
    row_prefix = Gtk.Template.Child()

    def __init__(
        self,
        window,
        database_entry: UmuDatabaseEntry | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.window = window
        self.repository = window.manager.umu_repository
        self.database_entry = database_entry or UmuDatabaseEntry(
            title=_("Custom Windows Game"),
            store="none",
            codename="custom",
            umu_id="umu-default",
        )
        self.custom = database_entry is None
        self.installer = None
        self.executable = None
        self.game = None
        self.proton = window.settings.get_string("umu-proton") or DEFAULT_PROTON_VALUE
        self._pulse_source = None
        self._stop_requested = False
        self._install_status = None

        self.source_modes.append(_("Run an Installer"))
        self.source_modes.append(_("Use a Portable Executable"))
        self.entry_name.set_text("" if self.custom else self.database_entry.title)
        self.status_intro.set_title(self.database_entry.title)
        if self.custom:
            self.status_intro.set_description(
                _(
                    "Choose the Windows installer and Bottles will create a "
                    "separate Proton prefix for the game."
                )
            )
            identity = _("No game-specific fixes")
            store = _("Not specified")
        else:
            self.status_intro.set_description(
                _(
                    "Bottles found a compatibility profile for this game and "
                    "will apply it automatically."
                )
            )
            identity = _("Available")
            store = _store_title(self.database_entry.store)
        self.row_identity.set_subtitle(identity)
        self.row_store.set_subtitle(store)
        self.row_setup_identity.set_subtitle(identity)
        self.row_setup_store.set_subtitle(store)
        self.label_proton.set_label(
            _proton_title(window.manager.umu_proton_catalog, self.proton)
        )

        self.btn_back.connect("clicked", self.__back)
        self.btn_next.connect("clicked", self.__next)
        self.btn_installer.connect("clicked", self.__choose_source_file)
        self.btn_executable.connect("clicked", self.__choose_executable)
        self.btn_done.connect("clicked", lambda *_args: self.close())
        self.btn_retry.connect("clicked", self.__retry)
        self.row_proton.connect("activated", self.__choose_proton)
        self.combo_source.connect("notify::selected", self.__source_changed)
        self.entry_name.connect("changed", self.__update_navigation)
        self.__set_page("intro")

    @property
    def __portable(self):
        return self.combo_source.get_selected() == 1

    def __source_changed(self, *_args):
        self.installer = None
        self.row_installer_validation.set_visible(False)
        if self.__portable:
            self.page_files.set_title(_("Choose the Game Executable"))
            self.page_files.set_description(
                _("Select the portable Windows executable for this game.")
            )
            self.row_installer.set_title(_("Portable Executable"))
            self.row_installer.set_subtitle(
                _("Select the .exe that starts the game.")
            )
        else:
            self.page_files.set_title(_("Choose the Installer"))
            self.page_files.set_description(
                _("Select the installer you downloaded for this game.")
            )
            self.row_installer.set_title(_("Installer File"))
            self.row_installer.set_subtitle(
                _("Select a Windows .exe or .msi installer.")
            )
        self.__update_navigation()

    def __set_page(self, page):
        self.stack.set_visible_child_name(page)
        subtitles = {
            "intro": _("Introduction"),
            "installer": _("Game Files"),
            "setup": _("Setup"),
            "installing": _("Installation"),
            "executable": _("Game Executable"),
            "complete": _("Completed"),
            "error": _("Installation Failed"),
        }
        self.window_title.set_subtitle(subtitles[page])

        self.btn_back.set_visible(page in ("intro", "installer", "setup", "error"))
        self.btn_next.set_visible(
            page in ("intro", "installer", "setup", "executable")
        )
        back_labels = {
            "intro": _("_Cancel"),
            "installing": _("_Stop"),
            "error": _("_Close"),
        }
        self.btn_back.set_label(back_labels.get(page, _("_Back")))
        self.btn_back.set_sensitive(True)
        labels = {
            "intro": _("_Continue"),
            "installer": _("_Continue"),
            "setup": _("_Add") if self.__portable else _("_Install"),
            "executable": _("_Finish"),
        }
        if page in labels:
            self.btn_next.set_label(labels[page])
        self.__update_navigation()

    def __update_navigation(self, *_args):
        page = self.stack.get_visible_child_name()
        sensitive = True
        if page == "installer":
            sensitive = self.installer is not None
        elif page == "setup":
            sensitive = bool(self.entry_name.get_text().strip() and self.proton)
        elif page == "executable":
            sensitive = self.executable is not None
        self.btn_next.set_sensitive(sensitive)

    def __back(self, *_args):
        page = self.stack.get_visible_child_name()
        if page == "intro":
            self.close()
        elif page == "installer":
            self.__set_page("intro")
        elif page == "setup":
            self.__set_page("installer")
        elif page == "installing":
            executor = self.window.manager.get_umu_executor(for_launch=False)
            if executor is None or self.game is None:
                return
            self._stop_requested = True
            self.btn_back.set_sensitive(False)
            self.btn_back.set_label(_("Stopping..."))

            def complete(stopped, error=False):
                if self.stack.get_visible_child_name() != "installing":
                    return
                if error or not stopped:
                    self._stop_requested = False
                    self.btn_back.set_sensitive(True)
                    self.btn_back.set_label(_("_Stop"))
                    self.window.show_toast(_("The installer could not be stopped."))

            RunAsync(
                executor.terminate,
                callback=complete,
                game_or_process=self.game,
            )
        elif page == "error":
            self.close()

    def __next(self, *_args):
        page = self.stack.get_visible_child_name()
        if page == "intro":
            self.__set_page("installer")
        elif page == "installer" and self.installer is not None:
            self.__set_page("setup")
        elif page == "setup":
            if self.__portable:
                self.__add_portable_game()
            else:
                self.__start_installation()
        elif page == "executable" and self.executable is not None:
            self.__finish()

    def __choose_source_file(self, *_args):
        def selected(dialog, result):
            try:
                file = dialog.open_finish(result)
                path = file.get_path()
                if path is None:
                    return
                allowed = {".exe"} if self.__portable else {".exe", ".msi"}
                self.installer = _validate_windows_file(path, allowed)
            except (GLib.Error, ValueError) as error:
                if isinstance(error, ValueError):
                    self.window.show_toast(str(error))
                return
            self.row_installer.set_subtitle(str(self.installer))
            self.row_installer_validation.set_title(
                _("Valid Windows executable")
                if self.__portable
                else _("Valid Windows installer")
            )
            self.row_installer_validation.set_visible(True)
            self.__update_navigation()

        patterns = ("*.exe", "*.EXE")
        title = _("Windows Executables")
        if not self.__portable:
            patterns += ("*.msi", "*.MSI")
            title = _("Windows Installers")
        filters, default_filter = _windows_file_filters(title, patterns)
        Gtk.FileDialog(
            title=_("Select a Windows Program"),
            filters=filters,
            default_filter=default_filter,
        ).open(self.window, callback=selected)

    def __choose_proton(self, *_args):
        UmuProtonDialog(
            self.window,
            self.proton,
            self.__set_proton,
        ).present(self)

    def __set_proton(self, value, title):
        self.proton = value
        self.label_proton.set_label(title)
        self.__update_navigation()

    def __new_game(self, state):
        proton = self.window.manager.umu_proton_catalog.pin_value(self.proton)
        game = self.repository.new_game(
            self.entry_name.get_text().strip(),
            self.installer,
            proton=proton,
            game_id=self.database_entry.umu_id,
            store=self.database_entry.store,
        )
        dependency_tool = self.window.settings.get_string("umu-dependency-tool")
        extra = {
            **game.extra,
            "dependency_tool": dependency_tool,
            "source_mode": "portable" if self.__portable else "installer",
        }
        if not self.__portable:
            extra["installer"] = str(self.installer)
        return self.repository.update(game, extra=extra, state=state)

    def __add_portable_game(self):
        try:
            self.game = self.__new_game("ready")
        except (ValueError, UmuRepositoryError) as error:
            self.window.show_toast(str(error))
            return
        LibraryManager().sync_umu_game(self.game)
        self.window.update_umu_views()
        self.status_complete.set_description(
            _("{0} is now available in the Library.").format(self.game.name)
        )
        self.__set_page("complete")

    def __start_installation(self):
        if self.window.manager.get_umu_executor() is None:
            self.window.show_umu_unavailable()
            return
        try:
            if self.game is None:
                self.game = self.__new_game("installing")
            else:
                self.game = self.repository.update(self.game, state="installing")
        except (ValueError, UmuRepositoryError) as error:
            self.window.show_toast(str(error))
            return

        LibraryManager().sync_umu_game(self.game)
        self.window.update_umu_views()
        self._stop_requested = False
        self._install_status = None
        self.set_can_close(False)
        self.__set_install_phase(0)
        self.__set_page("installing")
        self._pulse_source = GLib.timeout_add(100, self.__pulse)
        RunAsync(self.__run_installer, callback=self.__installation_finished)

    def __pulse(self):
        self.progress_install.pulse()
        executor = self.window.manager.get_umu_executor(for_launch=False)
        if executor is None or self.game is None:
            return GLib.SOURCE_CONTINUE
        status = executor.status_for(self.game)
        if status == self._install_status:
            return GLib.SOURCE_CONTINUE
        self._install_status = status
        messages = {
            "downloading": (
                _("Downloading Required Files"),
                _("UMU is downloading Proton, its runtime or a game dependency."),
            ),
            "preparing": (
                _("Preparing the Game Environment"),
                _("UMU is verifying and extracting the required files."),
            ),
            "configuring": (
                _("Applying Compatibility Fixes"),
                _("UMU is installing the dependencies required by this game."),
            ),
        }
        if status == "running":
            self.__set_install_phase(1)
        elif status in messages:
            title, description = messages[status]
            self.label_install_title.set_label(title)
            self.label_install_description.set_label(description)
        return GLib.SOURCE_CONTINUE

    def __stop_pulse(self):
        if self._pulse_source is not None:
            GLib.source_remove(self._pulse_source)
            self._pulse_source = None

    def __set_install_phase(self, phase):
        spinners = (self.spinner_prepare, self.spinner_run, self.spinner_finish)
        checks = (self.check_prepare, self.check_run, self.check_finish)
        for index, spinner in enumerate(spinners):
            spinner.set_visible(index == phase)
            spinner.set_spinning(index == phase)
            checks[index].set_visible(index < phase)

        titles = (
            _("Preparing and Running Installer"),
            _("Installer Running"),
            _("Finishing Setup"),
        )
        descriptions = (
            _(
                "Bottles may download Proton and its runtime first. Complete "
                "and close the Windows installer to continue."
            ),
            _("Complete the installer window, then close it to continue."),
            _("Bottles is saving the managed game environment."),
        )
        if phase < len(titles):
            self.label_install_title.set_label(titles[phase])
            self.label_install_description.set_label(descriptions[phase])
        return GLib.SOURCE_REMOVE

    def __run_installer(self):
        executor = self.window.manager.get_umu_executor()
        if executor is None:
            raise UmuRepositoryError("UMU is not available")
        executor.run(self.game)
        GLib.idle_add(self.__show_installer_stop)
        return executor.wait(self.game)

    def __show_installer_stop(self):
        if self.stack.get_visible_child_name() == "installing":
            self.btn_back.set_label(_("_Stop"))
            self.btn_back.set_sensitive(True)
            self.btn_back.set_visible(True)
        return GLib.SOURCE_REMOVE

    def __installation_finished(self, return_code, error=False):
        self.__stop_pulse()
        self.set_can_close(True)
        stopped = self._stop_requested and not error
        success = not stopped and not error and return_code == 0
        try:
            state = "stopped" if stopped else "draft" if success else "failed"
            self.game = self.repository.update(self.game, state=state)
            LibraryManager().sync_umu_game(self.game)
        except UmuRepositoryError as update_error:
            error = update_error
            success = False

        self.window.update_umu_views()
        if stopped:
            self.status_error.set_title(_("Installation Stopped"))
            self.status_error.set_description(
                _("The installer was stopped. You can try again or close this setup.")
            )
            self.__set_page("error")
            self.window_title.set_subtitle(_("Installation Stopped"))
            return
        if not success:
            self.status_error.set_title(_("Installation Failed"))
            if error:
                message = str(error)
            elif return_code is None:
                message = _("The installer stopped without returning a result.")
            else:
                message = _("The installer exited with status {0}.").format(
                    return_code
                )
            self.status_error.set_description(message)
            self.__set_page("error")
            return

        self.__set_install_phase(2)
        self.__set_install_phase(3)
        prefix = self.repository.prefix_path(self.game)
        self.row_prefix.set_subtitle(str(prefix))
        self.__set_page("executable")

    def __retry(self, *_args):
        self.__start_installation()

    def __choose_executable(self, *_args):
        def selected(dialog, result):
            try:
                file = dialog.open_finish(result)
                path = file.get_path()
                if path is None:
                    return
                executable = _validate_windows_file(path, {".exe"})
                prefix = self.repository.prefix_path(self.game).resolve()
                executable.relative_to(prefix)
            except GLib.Error:
                return
            except (ValueError, OSError):
                self.window.show_toast(
                    _("Select a Windows executable inside the managed prefix.")
                )
                return
            self.executable = executable
            self.row_executable.set_subtitle(str(executable))
            self.row_executable_validation.set_visible(True)
            self.__update_navigation()

        filters, default_filter = _windows_file_filters(
            _("Windows Executables"),
            ("*.exe", "*.EXE"),
        )
        dialog = Gtk.FileDialog(
            title=_("Select the Game Executable"),
            filters=filters,
            default_filter=default_filter,
        )
        prefix = self.repository.prefix_path(self.game).joinpath("drive_c")
        if prefix.is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(str(prefix)))
        dialog.open(self.window, callback=selected)

    def __finish(self):
        try:
            self.game = self.repository.update(
                self.game,
                executable=self.executable,
                state="ready",
            )
        except UmuRepositoryError as error:
            self.window.show_toast(str(error))
            return
        LibraryManager().sync_umu_game(self.game)
        self.window.update_umu_views()
        self.status_complete.set_description(
            _("{0} is now available in the Library.").format(self.game.name)
        )
        self.__set_page("complete")


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-umu-add.ui")
class UmuAddGameDialog(Adw.Dialog):
    __gtype_name__ = "UmuAddGameDialog"

    btn_cancel = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    combo_mode = Gtk.Template.Child()
    group_setup = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    row_executable = Gtk.Template.Child()
    btn_executable = Gtk.Template.Child()
    row_prefix = Gtk.Template.Child()
    btn_prefix = Gtk.Template.Child()
    row_proton = Gtk.Template.Child()
    label_proton = Gtk.Template.Child()
    btn_proton = Gtk.Template.Child()
    entry_game_id = Gtk.Template.Child()
    combo_store = Gtk.Template.Child()
    modes = Gtk.Template.Child()
    stores = Gtk.Template.Child()

    def __init__(
        self,
        window,
        mode="install",
        detected_prefix=None,
        database_entry: UmuDatabaseEntry | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.window = window
        self.repository = window.manager.umu_repository
        self.executable = None
        self.prefix = None
        self.proton = window.settings.get_string("umu-proton") or DEFAULT_PROTON_VALUE
        self.importing = None

        for label in (_("Run an Installer"), _("Use an Existing Executable")):
            self.modes.append(label)
        for label in _store_labels():
            self.stores.append(label)

        self.label_proton.set_label(
            _proton_title(window.manager.umu_proton_catalog, self.proton)
        )
        detected = mode == "detected" and detected_prefix
        self.combo_mode.set_selected(1 if mode in ("import", "detected") else 0)
        if database_entry is not None:
            self.entry_name.set_text(database_entry.title)
            self.entry_game_id.set_text(database_entry.umu_id)
            _select_id(self.combo_store, STORE_IDS, database_entry.store)
            self.entry_game_id.set_sensitive(False)
            self.combo_store.set_sensitive(False)
        if detected:
            self.prefix = str(Path(detected_prefix).expanduser().resolve())
            if database_entry is None:
                self.entry_name.set_text(Path(self.prefix).name)
            self.row_prefix.set_subtitle(self.prefix)
            self.btn_prefix.set_sensitive(False)
            self.group_setup.set_visible(False)
            self.set_title(_("Finish Game Setup"))
        self.__mode_changed()

        self.btn_cancel.connect("clicked", lambda *_args: self.close())
        self.btn_add.connect("clicked", self.__add)
        self.btn_executable.connect("clicked", self.__choose_executable)
        self.btn_prefix.connect("clicked", self.__choose_prefix)
        self.btn_proton.connect("clicked", self.__choose_proton)
        self.combo_mode.connect("notify::selected", self.__mode_changed)
        self.entry_name.connect("changed", self.__validate)
        self.entry_game_id.connect("changed", self.__validate)

    def __mode_changed(self, *_args):
        importing = self.combo_mode.get_selected() == 1
        if self.importing is not None and self.importing != importing:
            self.executable = None
            self.prefix = None
            self.row_executable.set_subtitle(
                _("Choose the installed game executable.")
                if importing
                else _("Choose the game installer.")
            )
            self.row_prefix.set_subtitle(_("Choose an existing Proton prefix."))
        self.importing = importing
        self.row_executable.set_title(
            _("Game Executable") if importing else _("Installer")
        )
        self.row_executable.set_subtitle(
            _("Choose the installed game executable.")
            if importing
            else _("Choose the game installer.")
        )
        self.row_prefix.set_visible(importing)
        self.__validate()

    def __validate(self, *_args):
        valid = bool(
            self.entry_name.get_text().strip()
            and self.proton
            and self.entry_game_id.get_text().strip()
            and self.executable
        )
        if self.combo_mode.get_selected() == 1:
            valid = valid and bool(self.prefix)
        self.btn_add.set_sensitive(valid)

    def __choose_executable(self, *_args):
        def selected(dialog, result):
            try:
                file = dialog.open_finish(result)
            except GLib.Error:
                return
            path = file.get_path()
            if path is None:
                return
            importing = self.combo_mode.get_selected() == 1
            allowed = {".exe"} if importing else {".exe", ".msi"}
            try:
                executable = _validate_windows_file(path, allowed)
            except ValueError as error:
                self.window.show_toast(str(error))
                return
            if importing and self.prefix:
                try:
                    executable.relative_to(Path(self.prefix).resolve())
                except ValueError:
                    self.window.show_toast(
                        _("Select an executable inside the chosen Proton prefix.")
                    )
                    return
            self.executable = str(executable)
            self.row_executable.set_subtitle(self.executable)
            if not self.entry_name.get_text().strip():
                self.entry_name.set_text(executable.stem)
            self.__validate()

        importing = self.combo_mode.get_selected() == 1
        patterns = ("*.exe", "*.EXE")
        title = _("Windows Executables")
        if not importing:
            patterns += ("*.msi", "*.MSI")
            title = _("Windows Installers")
        filters, default_filter = _windows_file_filters(title, patterns)
        dialog = Gtk.FileDialog(
            title=title,
            filters=filters,
            default_filter=default_filter,
        )
        dialog.open(self.window, callback=selected)

    def __choose_prefix(self, *_args):
        def selected(dialog, result):
            try:
                file = dialog.select_folder_finish(result)
            except GLib.Error:
                return
            self.prefix = file.get_path()
            if self.prefix is None:
                return
            if self.executable:
                try:
                    Path(self.executable).resolve().relative_to(
                        Path(self.prefix).resolve()
                    )
                except ValueError:
                    self.executable = None
                    self.row_executable.set_subtitle(
                        _("Choose the installed game executable.")
                    )
                    self.window.show_toast(
                        _("Choose an executable inside the selected Proton prefix.")
                    )
            self.row_prefix.set_subtitle(self.prefix)
            self.__validate()

        Gtk.FileDialog(title=_("Select a Game Prefix")).select_folder(
            self.window, callback=selected
        )

    def __choose_proton(self, *_args):
        UmuProtonDialog(
            self.window,
            self.proton,
            self.__set_proton,
        ).present(self)

    def __set_proton(self, value, title):
        self.proton = value
        self.label_proton.set_label(title)
        self.__validate()

    def __add(self, *_args):
        if not self.btn_add.get_sensitive():
            return

        importing = self.combo_mode.get_selected() == 1
        try:
            proton = self.window.manager.umu_proton_catalog.pin_value(self.proton)
        except ValueError as error:
            self.window.show_toast(str(error))
            return
        game = self.repository.new_game(
            self.entry_name.get_text().strip(),
            self.executable,
            proton=proton,
            game_id=self.entry_game_id.get_text().strip(),
            store=_selected_id(self.combo_store, STORE_IDS),
        )
        dependency_tool = self.window.settings.get_string("umu-dependency-tool")
        extra = {
            **game.extra,
            "dependency_tool": dependency_tool,
            "source_mode": "imported" if importing else "installer",
        }
        if not importing:
            extra["installer"] = str(self.executable)
        changes = {"extra": extra, "state": "ready" if importing else "installing"}
        if importing:
            changes["prefix"] = UmuPrefix(path=self.prefix, managed=False)

        try:
            game = self.repository.update(game, **changes)
        except UmuRepositoryError as error:
            self.window.show_toast(str(error))
            return

        LibraryManager().sync_umu_game(game)
        self.close()
        if not importing:
            self.window.launch_umu_installer(game)
        else:
            self.window.update_umu_views()


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-umu-game.ui")
class UmuGameDialog(Adw.Dialog):
    __gtype_name__ = "UmuGameDialog"

    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    row_executable = Gtk.Template.Child()
    btn_executable = Gtk.Template.Child()
    row_prefix = Gtk.Template.Child()
    btn_prefix = Gtk.Template.Child()
    row_proton = Gtk.Template.Child()
    label_proton = Gtk.Template.Child()
    btn_proton = Gtk.Template.Child()
    entry_game_id = Gtk.Template.Child()
    combo_store = Gtk.Template.Child()
    stores = Gtk.Template.Child()
    row_arguments = Gtk.Template.Child()
    row_working_directory = Gtk.Template.Child()
    btn_working_directory = Gtk.Template.Child()
    btn_working_directory_reset = Gtk.Template.Child()
    row_environment = Gtk.Template.Child()
    combo_dependency_tool = Gtk.Template.Child()
    dependency_tools = Gtk.Template.Child()
    row_dependency_selection = Gtk.Template.Child()
    row_installed_dependencies = Gtk.Template.Child()
    btn_choose_dependencies = Gtk.Template.Child()
    entry_winetricks = Gtk.Template.Child()
    row_install_dependencies = Gtk.Template.Child()
    btn_install_dependencies = Gtk.Template.Child()
    spinner_install_dependencies = Gtk.Template.Child()
    switch_delete_prefix = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()

    def __init__(self, window, game, **kwargs):
        super().__init__(**kwargs)
        self.window = window
        self.repository = window.manager.umu_repository
        self.game = game
        self.executable = str(game.executable)
        self.prefix = str(self.repository.prefix_path(game))
        self.prefix_managed = game.prefix.managed
        self.proton = game.proton
        self.working_directory = (
            str(game.working_directory) if game.working_directory else None
        )
        self.arguments = tuple(game.arguments)
        self.environment = dict(game.environment)
        self.installed_dependency_rows = []

        for label in _store_labels():
            self.stores.append(label)
        for label in _dependency_tool_labels():
            self.dependency_tools.append(label)

        self.entry_name.set_text(game.name)
        self.row_executable.set_subtitle(self.executable)
        self.row_prefix.set_subtitle(self.prefix)
        if self.prefix_managed:
            self.row_prefix.set_title(_("Managed Prefix"))
            self.btn_prefix.set_tooltip_text(_("Open Prefix Folder"))
        else:
            self.row_prefix.set_title(_("Game Prefix"))
            self.btn_prefix.set_tooltip_text(_("Choose Prefix"))
        self.label_proton.set_label(
            _proton_title(window.manager.umu_proton_catalog, self.proton)
        )
        self.entry_game_id.set_text(game.game_id)
        _select_id(self.combo_store, STORE_IDS, game.store)
        self.__update_arguments()
        self.__update_environment()
        self.__update_working_directory()
        self.switch_delete_prefix.set_visible(game.prefix.managed)
        _select_id(
            self.combo_dependency_tool,
            DEPENDENCY_TOOL_IDS,
            game.extra.get(
                "dependency_tool",
                window.settings.get_string("umu-dependency-tool"),
            ),
        )

        self.btn_cancel.connect("clicked", lambda *_args: self.close())
        self.btn_save.connect("clicked", self.__save)
        self.entry_name.connect("changed", self.__validate_settings)
        self.entry_game_id.connect("changed", self.__validate_settings)
        self.btn_executable.connect("clicked", self.__choose_executable)
        self.btn_prefix.connect("clicked", self.__prefix_action)
        self.btn_proton.connect("clicked", self.__choose_proton)
        self.row_arguments.connect("activated", self.__choose_arguments)
        self.row_environment.connect("activated", self.__choose_environment)
        self.btn_working_directory.connect("clicked", self.__choose_working_directory)
        self.btn_working_directory_reset.connect(
            "clicked", self.__reset_working_directory
        )
        self.btn_install_dependencies.connect("clicked", self.__install_dependencies)
        self.btn_choose_dependencies.connect(
            "clicked", self.__choose_dependencies
        )
        self.combo_dependency_tool.connect(
            "notify::selected", self.__dependency_tool_changed
        )
        self.entry_winetricks.connect("changed", self.__dependency_tool_changed)
        self.btn_remove.connect("clicked", self.__confirm_remove)
        self.__validate_settings()
        self.__update_installed_dependencies()
        self.__dependency_tool_changed()

    def __update_installed_dependencies(self):
        dependencies = self.game.extra.get("installed_dependencies", [])
        winetricks = self.game.extra.get("installed_winetricks", [])
        for row in self.installed_dependency_rows:
            self.row_installed_dependencies.remove(row)
        self.installed_dependency_rows = []

        for name in sorted(dependencies):
            metadata = self.window.manager.supported_dependencies.get(name, {})
            row = Adw.ActionRow(
                title=name,
                subtitle=metadata.get("Description", _("Bottles Dependencies")),
                use_markup=False,
            )
            category = metadata.get("Category")
            if category:
                label = Gtk.Label(label=category, valign=Gtk.Align.CENTER)
                label.add_css_class("tag")
                label.add_css_class("caption")
                row.add_suffix(label)
            row.add_css_class("property")
            self.row_installed_dependencies.add_row(row)
            self.installed_dependency_rows.append(row)

        for name in sorted(winetricks):
            row = Adw.ActionRow(title=name, subtitle="Winetricks", use_markup=False)
            row.add_css_class("property")
            self.row_installed_dependencies.add_row(row)
            self.installed_dependency_rows.append(row)

        count = len(self.installed_dependency_rows)
        self.row_installed_dependencies.set_visible(bool(count))
        self.row_installed_dependencies.set_subtitle(str(count))

    def __validate_settings(self, *_args):
        rows = (
            (self.entry_name, bool(self.entry_name.get_text().strip())),
            (self.entry_game_id, bool(self.entry_game_id.get_text().strip())),
        )
        executable_valid = bool(self.executable)
        self.btn_save.set_sensitive(
            all(valid for _row, valid in rows) and executable_valid
        )
        for row, valid in rows:
            if valid:
                row.remove_css_class("error")
            else:
                row.add_css_class("error")
        if executable_valid:
            self.row_executable.remove_css_class("error")
        else:
            self.row_executable.add_css_class("error")

    def __choose_executable(self, *_args):
        def selected(dialog, result):
            try:
                file = dialog.open_finish(result)
            except GLib.Error:
                return
            path = file.get_path()
            if path is None:
                return
            try:
                executable = _validate_windows_file(path, {".exe"})
            except ValueError as error:
                self.window.show_toast(str(error))
                return
            source_mode = self.game.extra.get("source_mode")
            require_managed_executable = source_mode in ("installer", "imported")
            if source_mode is None:
                require_managed_executable = bool(
                    self.game.extra.get("installer") or not self.game.prefix.managed
                )
            try:
                if require_managed_executable:
                    executable.relative_to(Path(self.prefix).resolve())
            except (ValueError, OSError):
                self.window.show_toast(
                    _("Select a valid Windows executable inside the game prefix.")
                )
                return
            self.executable = str(executable)
            self.row_executable.set_subtitle(self.executable)
            self.__validate_settings()

        filters, default_filter = _windows_file_filters(
            _("Windows Executables"),
            ("*.exe", "*.EXE"),
        )
        dialog = Gtk.FileDialog(
            title=_("Select a Windows Executable"),
            filters=filters,
            default_filter=default_filter,
        )
        dialog.open(self.window, callback=selected)

    def __prefix_action(self, *_args):
        if self.prefix_managed:
            ManagerUtils.open_filemanager(path_type="custom", custom_path=self.prefix)
            return
        self.__choose_prefix()

    def __choose_prefix(self, *_args):
        def selected(dialog, result):
            try:
                file = dialog.select_folder_finish(result)
            except GLib.Error:
                return
            path = file.get_path()
            if path:
                prefix = str(Path(path).resolve())
                if self.executable:
                    try:
                        Path(self.executable).resolve().relative_to(prefix)
                    except ValueError:
                        self.executable = ""
                        self.row_executable.set_subtitle(
                            _("Choose an executable inside the game prefix.")
                        )
                        self.window.show_toast(
                            _(
                                "Choose the game executable again because the "
                                "prefix changed."
                            )
                        )
                self.prefix = prefix
                self.prefix_managed = False
                self.row_prefix.set_subtitle(prefix)
                self.__validate_settings()

        Gtk.FileDialog(title=_("Select a Game Prefix")).select_folder(
            self.window, callback=selected
        )

    def __choose_proton(self, *_args):
        UmuProtonDialog(
            self.window,
            self.proton,
            self.__set_proton,
        ).present(self)

    def __set_proton(self, value, title):
        self.proton = value
        self.label_proton.set_label(title)

    def __choose_arguments(self, *_args):
        UmuArgumentsDialog(
            self.window,
            self.arguments,
            self.__set_arguments,
        ).present(self)

    def __set_arguments(self, arguments):
        self.arguments = tuple(arguments)
        self.__update_arguments()

    def __update_arguments(self):
        self.row_arguments.set_subtitle(
            shlex.join(self.arguments) if self.arguments else _("None")
        )

    def __choose_environment(self, *_args):
        UmuEnvironmentDialog(
            self.window,
            self.environment,
            self.__set_environment,
        ).present(self)

    def __set_environment(self, environment):
        self.environment = dict(environment)
        self.__update_environment()

    def __update_environment(self):
        count = len(self.environment)
        self.row_environment.set_subtitle(
            ngettext("{0} variable", "{0} variables", count).format(count)
            if count
            else _("None")
        )

    def __choose_working_directory(self, *_args):
        def selected(dialog, result):
            try:
                file = dialog.select_folder_finish(result)
            except GLib.Error:
                return
            self.working_directory = file.get_path()
            self.__update_working_directory()

        Gtk.FileDialog(title=_("Select a Working Directory")).select_folder(
            self.window, callback=selected
        )

    def __reset_working_directory(self, *_args):
        self.working_directory = None
        self.__update_working_directory()

    def __update_working_directory(self):
        if self.working_directory:
            self.row_working_directory.set_subtitle(self.working_directory)
            self.btn_working_directory_reset.set_visible(True)
            return
        self.row_working_directory.set_subtitle(_("Use the executable directory."))
        self.btn_working_directory_reset.set_visible(False)

    def __save(self, *_args):
        try:
            prefix = UmuPrefix(
                path=(self.game.prefix.path if self.prefix_managed else self.prefix),
                managed=self.prefix_managed,
                extra=self.game.prefix.extra,
            )
            extra = {
                **self.game.extra,
                "dependency_tool": _selected_id(
                    self.combo_dependency_tool, DEPENDENCY_TOOL_IDS
                ),
            }
            state = self.game.state
            installer = self.game.extra.get("installer")
            if state in ("draft", "failed", "stopped") and (
                not installer or str(self.executable) != installer
            ):
                state = "ready"
            self.game = self.repository.update(
                self.game,
                name=self.entry_name.get_text().strip(),
                executable=Path(self.executable),
                prefix=prefix,
                proton=self.window.manager.umu_proton_catalog.pin_value(self.proton),
                game_id=self.entry_game_id.get_text().strip(),
                store=_selected_id(self.combo_store, STORE_IDS),
                arguments=self.arguments,
                working_directory=(
                    Path(self.working_directory) if self.working_directory else None
                ),
                environment=self.environment,
                extra=extra,
                state=state,
            )
        except (ValueError, UmuRepositoryError) as error:
            self.window.show_toast(str(error))
            return

        LibraryManager().sync_umu_game(self.game)
        self.window.update_umu_views()
        self.close()

    def __install_dependencies(self, *_args):
        tool = "winetricks"
        try:
            names = tuple(shlex.split(self.entry_winetricks.get_text()))
        except ValueError as error:
            self.window.show_toast(str(error))
            return
        if not names:
            self.window.show_toast(_("Enter at least one Winetricks verb."))
            return

        executor = self.window.manager.get_umu_executor()
        if executor is None:
            self.window.show_umu_unavailable()
            return

        self.btn_install_dependencies.set_sensitive(False)
        self.btn_install_dependencies.set_label(_("Installing..."))
        self.spinner_install_dependencies.set_visible(True)
        self.spinner_install_dependencies.start()
        self.row_install_dependencies.set_subtitle(_("Installing Winetricks verbs..."))
        self.set_can_close(False)
        self.btn_save.set_sensitive(False)
        self.btn_cancel.set_sensitive(False)
        self.btn_remove.set_sensitive(False)
        self.combo_dependency_tool.set_sensitive(False)
        self.btn_choose_dependencies.set_sensitive(False)
        self.entry_winetricks.set_sensitive(False)

        def install():
            current = self.repository.load(self.game.id)
            current = self.repository.update(
                current,
                extra={**current.extra, "dependency_tool": tool},
            )
            self.game = current
            executor.install_winetricks(current, names)
            success = executor.wait(current) == 0
            if success:
                current = self.repository.load(current.id)
                installed = list(current.extra.get("installed_winetricks", []))
                installed.extend(name for name in names if name not in installed)
                current = self.repository.update(
                    current,
                    extra={
                        **current.extra,
                        "dependency_tool": tool,
                        "installed_winetricks": installed,
                    },
                )
                self.game = current
            return success, ""

        def complete(result, error=False):
            self.btn_install_dependencies.set_label(_("Install"))
            self.btn_install_dependencies.set_sensitive(True)
            self.spinner_install_dependencies.stop()
            self.spinner_install_dependencies.set_visible(False)
            self.set_can_close(True)
            self.__validate_settings()
            self.btn_cancel.set_sensitive(True)
            self.btn_remove.set_sensitive(True)
            self.combo_dependency_tool.set_sensitive(True)
            self.btn_choose_dependencies.set_sensitive(True)
            self.entry_winetricks.set_sensitive(True)
            success, message = result if result else (False, "")
            if success:
                self.entry_winetricks.set_text("")
                self.__update_installed_dependencies()
                self.__dependency_tool_changed()
                self.window.show_toast(_("Winetricks verbs installed."))
            else:
                self.__dependency_tool_changed()
                self.window.show_toast(message or _("Winetricks installation failed."))

        RunAsync(install, callback=complete)

    def __choose_dependencies(self, *_args):
        UmuDependencyDialog(
            self.window,
            self.game,
            self.__dependencies_installed,
        ).present(self)

    def __dependencies_installed(self, game):
        self.game = game
        self.__update_installed_dependencies()
        self.__dependency_tool_changed()

    def __dependency_tool_changed(self, *_args):
        winetricks = (
            _selected_id(self.combo_dependency_tool, DEPENDENCY_TOOL_IDS)
            == "winetricks"
        )
        self.row_dependency_selection.set_visible(not winetricks)
        self.entry_winetricks.set_visible(winetricks)
        self.row_install_dependencies.set_visible(winetricks)
        if winetricks:
            self.row_install_dependencies.set_subtitle(
                _("Enter one or more Winetricks verbs separated by spaces.")
            )
            has_selection = bool(self.entry_winetricks.get_text().strip())
        else:
            self.row_dependency_selection.set_subtitle(
                _("Browse dependencies that Bottles can install through UMU.")
            )
            has_selection = False
        self.btn_install_dependencies.set_sensitive(has_selection)

    def __confirm_remove(self, *_args):
        delete_prefix = (
            self.game.prefix.managed and self.switch_delete_prefix.get_active()
        )
        dialog = Adw.AlertDialog.new(
            _('Remove "{0}"?').format(self.game.name),
            (
                _(
                    "The game, its settings and its managed Proton prefix "
                    "will be deleted. This cannot be undone."
                )
                if delete_prefix
                else _(
                    "The game and its settings will be removed from Bottles. "
                    "Its files will be kept."
                )
            ),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        def response(_dialog, response_id):
            if response_id != "remove":
                return
            executor = self.window.manager.get_umu_executor(for_launch=False)
            if executor is not None and executor.is_running(self.game):
                self.window.show_toast(_("Stop the game before removing it."))
                return
            try:
                self.repository.delete(
                    self.game,
                    delete_prefix=delete_prefix,
                )
            except UmuRepositoryError as error:
                self.window.show_toast(str(error))
                return
            LibraryManager().remove_umu_game(str(self.game.id))
            self.window.update_umu_views()
            self.close()

        dialog.connect("response", response)
        dialog.present(self)
