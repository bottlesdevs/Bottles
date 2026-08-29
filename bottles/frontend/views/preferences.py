# preferences.py
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

import os
import subprocess
import webbrowser
from gettext import gettext as _
from gettext import ngettext
from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk

from bottles.backend.globals import Paths
from bottles.backend.managers.data import DataManager, UserDataKeys
from bottles.backend.state import EventManager, Events
from bottles.backend.utils.generic import sort_by_version
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.flatpak import resolve_bottles_directory
from bottles.frontend.utils.gtk import FONT_SCALE_VALUES
from bottles.frontend.utils.localization import (
    UI_LANGUAGES,
    get_ui_language_environment,
)
from bottles.frontend.utils.umu import UmuFrontendProvider
from bottles.frontend.widgets.component import ComponentEntry, ComponentExpander


@Gtk.Template(resource_path="/com/usebottles/bottles/preferences.ui")
class PreferencesWindow(Adw.PreferencesDialog):
    __gtype_name__ = "PreferencesWindow"

    # region Widgets
    installers_stack = Gtk.Template.Child()
    installers_spinner = Gtk.Template.Child()
    dlls_stack = Gtk.Template.Child()
    dlls_spinner = Gtk.Template.Child()
    cache_stack = Gtk.Template.Child()
    cache_spinner = Gtk.Template.Child()
    umu_stack = Gtk.Template.Child()
    umu_spinner = Gtk.Template.Child()
    status_umu_error = Gtk.Template.Child()
    btn_umu_error_retry = Gtk.Template.Child()

    row_theme = Gtk.Template.Child()
    switch_theme = Gtk.Template.Child()
    switch_notifications = Gtk.Template.Child()
    switch_component_updates = Gtk.Template.Child()
    switch_show_funding = Gtk.Template.Child()
    switch_force_offline = Gtk.Template.Child()
    switch_home_drive = Gtk.Template.Child()
    switch_temp = Gtk.Template.Child()
    switch_release_candidate = Gtk.Template.Child()
    switch_steam = Gtk.Template.Child()
    switch_auto_close = Gtk.Template.Child()
    switch_update_date = Gtk.Template.Child()
    switch_playtime_tracking = Gtk.Template.Child()
    switch_eagle_security = Gtk.Template.Child()
    switch_eagle_crash = Gtk.Template.Child()
    row_eagle_security = Gtk.Template.Child()
    switch_steam_programs = Gtk.Template.Child()
    switch_epic_games = Gtk.Template.Child()
    switch_ubisoft_connect = Gtk.Template.Child()
    combo_ui_language = Gtk.Template.Child()
    str_list_ui_languages = Gtk.Template.Child()
    combo_font_scale = Gtk.Template.Child()
    combo_audio_driver = Gtk.Template.Child()
    spin_eagle_limit = Gtk.Template.Child()
    list_runners = Gtk.Template.Child()
    list_dlls = Gtk.Template.Child()
    action_prerelease = Gtk.Template.Child()
    btn_bottles_path = Gtk.Template.Child()
    action_steam_proton = Gtk.Template.Child()
    btn_bottles_path_reset = Gtk.Template.Child()
    label_bottles_path = Gtk.Template.Child()
    btn_steam_proton_doc = Gtk.Template.Child()
    entry_personal_components = Gtk.Template.Child()
    entry_personal_dependencies = Gtk.Template.Child()
    entry_personal_installers = Gtk.Template.Child()
    template_cache_group = Gtk.Template.Child()
    label_cache_total_size = Gtk.Template.Child()
    label_cache_temp_size = Gtk.Template.Child()
    label_cache_templates_size = Gtk.Template.Child()
    btn_cache_clear_all = Gtk.Template.Child()
    btn_cache_clear_temp = Gtk.Template.Child()
    btn_cache_clear_templates = Gtk.Template.Child()
    row_umu_path = Gtk.Template.Child()
    row_umu_runtime = Gtk.Template.Child()
    row_umu_standard = Gtk.Template.Child()
    row_umu_launcher = Gtk.Template.Child()
    row_umu_proton = Gtk.Template.Child()
    label_umu_proton = Gtk.Template.Child()
    combo_umu_dependency = Gtk.Template.Child()
    label_umu_games = Gtk.Template.Child()
    label_umu_source = Gtk.Template.Child()
    label_umu_version = Gtk.Template.Child()
    btn_umu_refresh = Gtk.Template.Child()
    btn_umu_path = Gtk.Template.Child()
    btn_umu_path_change = Gtk.Template.Child()
    btn_umu_path_reset = Gtk.Template.Child()
    btn_umu_runtime = Gtk.Template.Child()
    btn_umu_standard = Gtk.Template.Child()

    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.settings = window.settings
        self.manager = window.manager
        self.umu_provider = UmuFrontendProvider.from_backend(self.manager)
        self.data = DataManager()
        self.style_manager = Adw.StyleManager.get_default()

        self.__audio_driver_values = [
            "default",
            "pulse",
            "alsa",
            "oss",
            "disabled",
        ]
        self.__updating_audio_driver = False
        self.__ui_language_values = [code for code, _name in UI_LANGUAGES]
        self.__updating_ui_language = False
        self.__updating_font_scale = False
        self.__updating_umu_settings = False
        self.__umu_dependency_values = ["bottles", "winetricks"]

        self.current_bottles_path = self.data.get(UserDataKeys.CustomBottlesPath)
        if self.current_bottles_path:
            self.label_bottles_path.set_label(
                os.path.basename(self.current_bottles_path)
            )
            self.btn_bottles_path_reset.set_visible(True)

        self.__personal_repo_rows = {
            "components": self.entry_personal_components,
            "dependencies": self.entry_personal_dependencies,
            "installers": self.entry_personal_installers,
        }
        stored_repositories = self.data.get(UserDataKeys.PersonalRepositories) or {}
        self.__personal_repo_values = {}
        for repo_name, row in self.__personal_repo_rows.items():
            repo_value = stored_repositories.get(repo_name, "")
            self.__personal_repo_values[repo_name] = repo_value
            row.set_text(repo_value)
            row.set_show_apply_button(False)
            row.connect("apply", self.__on_personal_repo_apply, repo_name)
            row.connect("changed", self.__on_personal_repo_changed, repo_name)

        self.__cache_registry = []
        self.__registry = []

        # bind widgets
        self.settings.bind(
            "dark-theme", self.switch_theme, "active", Gio.SettingsBindFlags.DEFAULT
        )
        self.settings.bind(
            "notifications",
            self.switch_notifications,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "show-component-updates",
            self.switch_component_updates,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "show-funding",
            self.switch_show_funding,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.switch_show_funding.connect(
            "notify::active", self.__funding_setting_changed
        )
        self.settings.bind(
            "playtime-enabled",
            self.switch_playtime_tracking,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "eagle-security-scan",
            self.switch_eagle_security,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "eagle-crash-detection",
            self.switch_eagle_crash,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        # warn visually (red row) when threat scanning is turned off
        self.switch_eagle_security.connect(
            "notify::active", self.__update_eagle_security_style
        )
        self.__update_eagle_security_style()
        self.settings.bind(
            "force-offline",
            self.switch_force_offline,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "disable-home-drive",
            self.switch_home_drive,
            "active",
            Gio.SettingsBindFlags.INVERT_BOOLEAN,
        )
        self.settings.bind(
            "temp", self.switch_temp, "active", Gio.SettingsBindFlags.DEFAULT
        )
        # Connect RC signal to another func
        self.settings.bind(
            "release-candidate",
            self.switch_release_candidate,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "steam-proton-support",
            self.switch_steam,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "auto-close-bottles",
            self.switch_auto_close,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "update-date",
            self.switch_update_date,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "steam-programs",
            self.switch_steam_programs,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "epic-games",
            self.switch_epic_games,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "ubisoft-connect",
            self.switch_ubisoft_connect,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )

        for index, (_code, name) in enumerate(UI_LANGUAGES):
            self.str_list_ui_languages.append(_(name) if index == 0 else name)
        self.__sync_ui_language_selection()
        self.combo_ui_language.connect(
            "notify::selected", self.__on_ui_language_selected
        )
        self.settings.connect(
            "changed::ui-language", self.__on_ui_language_setting_changed
        )

        self.__sync_font_scale_selection()
        self.combo_font_scale.connect("notify::selected", self.__on_font_scale_selected)
        self.settings.connect(
            "changed::font-scale", self.__on_font_scale_setting_changed
        )

        self.spin_eagle_limit.set_value(self.settings.get_int("eagle-scan-limit"))
        self.spin_eagle_limit.connect("notify::value", self.__on_eagle_limit_changed)

        self.__sync_audio_driver_selection()
        self.combo_audio_driver.connect(
            "notify::selected", self.__on_audio_driver_selected
        )
        self.settings.connect(
            "changed::audio-driver", self.__on_audio_driver_setting_changed
        )

        # setup loading screens
        self.installers_stack.set_visible_child_name("installers_loading")
        self.installers_spinner.start()
        self.dlls_stack.set_visible_child_name("dlls_loading")
        self.dlls_spinner.start()
        self.cache_stack.set_visible_child_name("cache_loading")
        self.cache_spinner.start()

        if not self.manager.utils_conn.status:
            self.installers_stack.set_visible_child_name("installers_offline")
            self.dlls_stack.set_visible_child_name("dlls_offline")

        RunAsync(self.ui_update)

        # connect signals
        self.settings.connect("changed::dark-theme", self.__toggle_night)
        self.settings.connect("changed::release-candidate", self.__toggle_rc)
        self.settings.connect("changed::update-date", self.__toggle_update_date)
        self.settings.connect(
            "changed::show-component-updates", self.__toggle_component_updates
        )
        self.btn_bottles_path.connect("clicked", self.__choose_bottles_path)
        self.btn_bottles_path_reset.connect("clicked", self.__reset_bottles_path)
        self.btn_steam_proton_doc.connect("clicked", self.__open_steam_proton_doc)
        self.btn_cache_clear_all.connect("clicked", self.__confirm_clear_all_caches)
        self.btn_cache_clear_temp.connect("clicked", self.__confirm_clear_temp_cache)
        self.btn_cache_clear_templates.connect(
            "clicked", self.__confirm_clear_templates_cache
        )
        self.btn_umu_refresh.connect("clicked", self.__refresh_umu)
        self.btn_umu_error_retry.connect("clicked", self.__refresh_umu)
        self.btn_umu_path.connect("clicked", self.__open_umu_path)
        self.btn_umu_path_change.connect("clicked", self.__choose_umu_path)
        self.btn_umu_path_reset.connect("clicked", self.__reset_umu_path)
        self.btn_umu_runtime.connect("clicked", self.__open_umu_runtime)
        self.btn_umu_standard.connect("clicked", self.__open_umu_standard)
        self.row_umu_proton.connect("activated", self.__choose_umu_proton)
        self.combo_umu_dependency.connect(
            "notify::selected", self.__on_umu_dependency_selected
        )

        if not self.manager.steam_manager.is_steam_supported:
            self.switch_steam.set_sensitive(False)
            self.action_steam_proton.set_tooltip_text(
                _("Steam was not found or Bottles does not have enough permissions.")
            )
            self.btn_steam_proton_doc.set_visible(True)

        if not self.style_manager.get_system_supports_color_schemes():
            self.row_theme.set_visible(True)

        self.populate_cache_list()
        self.__update_umu_status()

    def empty_list(self):
        for w in self.__registry:
            parent = w.get_parent()
            if parent:
                parent.remove(w)
        self.__registry = []

    def __update_eagle_security_style(self, *_args):
        if self.switch_eagle_security.get_active():
            self.row_eagle_security.remove_css_class("error")
            self.row_eagle_security.set_subtitle(
                _("Check executables for malware patterns before running them.")
            )
        else:
            self.row_eagle_security.add_css_class("error")
            self.row_eagle_security.set_subtitle(
                _("Disabled. Executables will run without being checked for threats.")
            )

    def __funding_setting_changed(self, switch, _pspec):
        if switch.get_active():
            self.data.remove(UserDataKeys.FundingDismissed)

    def ui_update(self):
        # Show locally installed runners/DLLs right away so the pages never get
        # stuck on the loading spinner when the online catalog is slow or
        # unreachable (the lists are read from disk, no network needed).
        def render():
            self.empty_list()
            self.populate_runners_list()
            self.populate_dlls_list()
            self.populate_cache_list()
            self.dlls_stack.set_visible_child_name("dlls_list")

        GLib.idle_add(render)

        # then refresh once the online or cached catalog has been organized
        EventManager.wait(Events.ComponentsOrganizing)
        GLib.idle_add(render)

    def __toggle_night(self, widget, state):
        if self.settings.get_boolean("dark-theme"):
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)

    def __toggle_update_date(self, widget, state):
        self.window.page_list.update_bottles_list()

    def __toggle_component_updates(self, *_args):
        if hasattr(self.window, "page_list"):
            self.window.page_list.update_component_updates_banner()
        if hasattr(self.window, "page_details"):
            self.window.page_details.view_bottle.populate_updates()

    def __toggle_rc(self, widget, state):
        self.ui_update()

    def __on_eagle_limit_changed(self, spin_row, _pspec):
        self.settings.set_int("eagle-scan-limit", int(spin_row.get_value()))

    def __open_steam_proton_doc(self, widget):
        webbrowser.open(
            "https://docs.usebottles.com/flatpak/cant-enable-steam-proton-manager"
        )

    def __update_umu_status(self, refresh=False):
        self.umu_stack.set_visible_child_name("umu_loading")
        self.umu_spinner.start()
        RunAsync(
            self.umu_provider.get_status,
            callback=self.__apply_umu_status,
            refresh=refresh,
        )

    def __apply_umu_status(self, status, error=False):
        self.umu_spinner.stop()
        if error or not status:
            self.status_umu_error.set_description(
                str(error) if error else _("No status information was returned.")
            )
            self.umu_stack.set_visible_child_name("umu_error")
            return
        if not status["available"]:
            self.umu_stack.set_visible_child_name("umu_unavailable")
            return

        installation = status["installation"]
        if installation is None:
            self.row_umu_launcher.add_css_class("error")
            self.row_umu_launcher.set_subtitle(
                status["error"] or _("No usable UMU launcher was found.")
            )
            self.label_umu_source.set_label(_("Unavailable"))
            self.label_umu_version.set_visible(False)
        else:
            source_labels = {
                "system": _("System"),
                "bundled": _("Bundled"),
                "explicit": _("Custom"),
                "managed": _("Managed"),
            }
            self.row_umu_launcher.remove_css_class("error")
            self.row_umu_launcher.set_subtitle(str(installation.path))
            self.label_umu_source.set_label(
                source_labels.get(installation.source, installation.source)
            )
            self.label_umu_version.set_label(installation.version)
            self.label_umu_version.set_visible(True)

        count = status["game_count"]
        game_count = ngettext("{0} game", "{0} games", count).format(count)
        discovered = status["discovered_count"]
        if discovered:
            game_count = _("{0}, {1} detected").format(game_count, discovered)
        self.label_umu_games.set_label(game_count)
        self.row_umu_path.set_subtitle(status["root"])
        self.btn_umu_path.set_sensitive(bool(status["root"]))
        self.btn_umu_path_reset.set_visible(
            bool(self.settings.get_string("umu-data-path"))
        )
        self.row_umu_runtime.set_subtitle("~/.local/share/umu")
        self.btn_umu_runtime.set_sensitive(bool(status["runtime_root"]))
        self.row_umu_standard.set_subtitle("~/Games/umu")
        self.btn_umu_standard.set_sensitive(bool(status["standard_prefix_root"]))
        self.__updating_umu_settings = True
        self.label_umu_proton.set_label(
            self.__umu_proton_title(status["default_proton"])
        )
        dependency_tool = status["dependency_tool"]
        try:
            dependency_index = self.__umu_dependency_values.index(dependency_tool)
        except ValueError:
            dependency_index = 0
        self.combo_umu_dependency.set_selected(dependency_index)
        self.__updating_umu_settings = False
        self.umu_stack.set_visible_child_name("umu_available")

    def __refresh_umu(self, *_args):
        self.__update_umu_status(refresh=True)
        if hasattr(self.window, "page_list"):
            self.window.page_list.update_bottles_list(refresh_updates=False)

    def __open_umu_path(self, *_args):
        root = str(self.umu_provider.repository.root)
        if root:
            ManagerUtils.open_filemanager(path_type="custom", custom_path=root)

    def __open_umu_runtime(self, *_args):
        root = str(Path.home().joinpath(".local", "share", "umu"))
        ManagerUtils.open_filemanager(path_type="custom", custom_path=root)

    def __open_umu_standard(self, *_args):
        root = str(Path.home().joinpath("Games", "umu"))
        ManagerUtils.open_filemanager(path_type="custom", custom_path=root)

    def __choose_umu_path(self, *_args):
        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = resolve_bottles_directory(self.window, dialog.get_file().get_path())
            if path is None:
                return
            self.__change_umu_path(path)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select UMU Data Path"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            parent=self.window,
        )
        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def __reset_umu_path(self, *_args):
        self.__change_umu_path("")

    def __change_umu_path(self, value):
        if value == self.settings.get_string("umu-data-path"):
            return

        def apply():
            self.settings.set_string("umu-data-path", value)
            self.row_umu_path.set_subtitle(
                value or str(Path(Paths.base).joinpath("umu"))
            )
            self.btn_umu_path_reset.set_visible(bool(value))
            self.prompt_restart(force=True)

        if not self.umu_provider.repository.list_games():
            apply()
            return

        warning = Adw.AlertDialog.new(
            _("Change the UMU Data Folder?"),
            _(
                "Existing games will not be moved. They will disappear from "
                "Bottles until you switch back to the current folder."
            ),
        )
        warning.add_response("cancel", _("Cancel"))
        warning.add_response("change", _("Change"))
        warning.set_response_appearance(
            "change", Adw.ResponseAppearance.DESTRUCTIVE
        )

        def response(_dialog, response_id):
            if response_id == "change":
                apply()

        warning.connect("response", response)
        warning.present(self)

    def __umu_proton_title(self, value):
        for choice in self.manager.umu_proton_catalog.list_choices(
            include_unstable=True
        ):
            if choice.value == value:
                return choice.title
        return Path(value).name or value

    def __choose_umu_proton(self, *_args):
        from bottles.frontend.windows.umu import UmuProtonDialog

        UmuProtonDialog(
            self.window,
            self.settings.get_string("umu-proton"),
            self.__set_umu_proton,
        ).present(self)

    def __set_umu_proton(self, value, title):
        self.settings.set_string("umu-proton", value)
        self.label_umu_proton.set_label(title)

    def __on_umu_dependency_selected(self, combo, _pspec):
        if self.__updating_umu_settings:
            return
        index = combo.get_selected()
        if index < len(self.__umu_dependency_values):
            self.settings.set_string(
                "umu-dependency-tool", self.__umu_dependency_values[index]
            )

    def __choose_bottles_path(self, widget):
        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = resolve_bottles_directory(self.window, dialog.get_file().get_path())
            if path is None:
                return

            self.data.set(UserDataKeys.CustomBottlesPath, path)
            self.label_bottles_path.set_label(os.path.basename(path))
            self.btn_bottles_path_reset.set_visible(True)
            self.prompt_restart()

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Bottles Path"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            parent=self.window,
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def handle_restart(self, widget, response_id):
        if response_id == "restart":
            environment = get_ui_language_environment(
                self.settings.get_string("ui-language")
            )
            subprocess.Popen("sleep 1 && bottles & disown", shell=True, env=environment)
            self.window.proper_close()
        widget.destroy()

    def prompt_restart(self, force=False):
        needs_restart = force or (
            self.current_bottles_path != self.data.get(UserDataKeys.CustomBottlesPath)
        )

        if needs_restart:
            dialog = Adw.MessageDialog.new(
                self.window,
                _("Relaunch Bottles?"),
                _(
                    "Bottles will need to be relaunched to use this directory.\n\nBe sure to close every program launched from Bottles before relaunching Bottles, as not doing so can cause data loss, corruption and programs to malfunction."
                ),
            )
            dialog.add_response("dismiss", _("_Cancel"))
            dialog.add_response("restart", _("_Relaunch"))
            dialog.set_response_appearance(
                "restart", Adw.ResponseAppearance.DESTRUCTIVE
            )
            dialog.connect("response", self.handle_restart)
            dialog.present()

    def __reset_bottles_path(self, widget):
        self.data.remove(UserDataKeys.CustomBottlesPath)
        self.btn_bottles_path_reset.set_visible(False)
        self.label_bottles_path.set_label(_("(Default)"))
        self.prompt_restart()

    def __on_personal_repo_changed(self, row, repo_name):
        if row.get_text() == self.__personal_repo_values.get(repo_name, ""):
            row.set_show_apply_button(False)
        else:
            row.set_show_apply_button(True)

    def __on_personal_repo_apply(self, row, repo_name):
        new_value = row.get_text().strip()
        if new_value == self.__personal_repo_values.get(repo_name, ""):
            return

        self.__personal_repo_values[repo_name] = new_value
        self.__persist_personal_repositories()
        row.set_show_apply_button(False)
        self.prompt_restart(force=True)

    def __persist_personal_repositories(self):
        stored_values = {
            repo_name: value
            for repo_name, value in self.__personal_repo_values.items()
            if value
        }

        if stored_values:
            self.data.set(UserDataKeys.PersonalRepositories, stored_values)
        else:
            self.data.remove(UserDataKeys.PersonalRepositories)

    def __on_font_scale_setting_changed(self, *_args):
        GLib.idle_add(self.__sync_font_scale_selection)

    def __sync_font_scale_selection(self, *_args):
        scale = self.settings.get_double("font-scale")
        index = min(
            range(len(FONT_SCALE_VALUES)),
            key=lambda item: abs(FONT_SCALE_VALUES[item] - scale),
        )

        self.__updating_font_scale = True
        self.combo_font_scale.set_selected(index)
        self.__updating_font_scale = False

    def __on_font_scale_selected(self, combo, _pspec):
        if self.__updating_font_scale:
            return

        index = combo.get_selected()
        if index < 0 or index >= len(FONT_SCALE_VALUES):
            return

        self.settings.set_double("font-scale", FONT_SCALE_VALUES[index])

    def __on_audio_driver_setting_changed(self, *_args):
        GLib.idle_add(self.__sync_audio_driver_selection)

    def __on_ui_language_setting_changed(self, *_args):
        GLib.idle_add(self.__sync_ui_language_selection)

    def __sync_ui_language_selection(self, *_args):
        language = self.settings.get_string("ui-language")
        try:
            index = self.__ui_language_values.index(language)
        except ValueError:
            index = 0

        self.__updating_ui_language = True
        self.combo_ui_language.set_selected(index)
        self.__updating_ui_language = False

    def __on_ui_language_selected(self, combo, _pspec):
        if self.__updating_ui_language:
            return

        index = combo.get_selected()
        if index < 0 or index >= len(self.__ui_language_values):
            return

        language = self.__ui_language_values[index]
        if language == self.settings.get_string("ui-language"):
            return

        self.settings.set_string("ui-language", language)
        self.add_toast(
            Adw.Toast.new(_("Quit and reopen Bottles to apply the language."))
        )

    def __sync_audio_driver_selection(self, *_args):
        driver = self.settings.get_string("audio-driver")
        try:
            index = self.__audio_driver_values.index(driver)
        except ValueError:
            index = 0

        self.__updating_audio_driver = True
        self.combo_audio_driver.set_selected(index)
        self.__updating_audio_driver = False

    def __on_audio_driver_selected(self, combo, _pspec):
        if self.__updating_audio_driver:
            return

        index = combo.get_selected()
        if index < 0 or index >= len(self.__audio_driver_values):
            return

        driver = self.__audio_driver_values[index]
        self.__updating_audio_driver = True
        self.settings.set_string("audio-driver", driver)
        self.__updating_audio_driver = False

        RunAsync(self.manager.apply_audio_driver, driver=driver)

    def __display_unstable_candidate(self, component=["", {"Channel": "unstable"}]):
        return self.window.settings.get_boolean("release-candidate") or component[1][
            "Channel"
        ] not in ["rc", "unstable"]

    def __populate_component_list(
        self, component_type, supported_components, list_component
    ):
        offline_components = self.manager.get_offline_components(component_type)
        supported_component_items = list(supported_components.items())
        if self.__display_unstable_candidate():
            i, j = 0, 0
            while i <= len(supported_component_items):
                while j < len(offline_components) and (
                    i == len(supported_component_items)
                    or sort_by_version(
                        [offline_components[j], supported_component_items[i][0]]
                    )[0]
                    == offline_components[j]
                ):
                    offline_entry = [
                        offline_components[j],
                        {
                            "Installed": True,
                            "Channel": "unstable",
                            "Category": component_type,
                        },
                    ]
                    supported_component_items.insert(i, offline_entry)
                    j += 1
                i += 1
        count = 0
        for component in supported_component_items:
            if not self.__display_unstable_candidate(component):
                continue
            _entry = ComponentEntry(self.window, component, component_type)
            if hasattr(list_component, "add_row"):
                list_component.add_row(_entry)
            else:
                list_component.add(_entry)
            self.__registry.append(_entry)
            count += 1

        return count

    def populate_dlls_list(self):
        dll_components = [
            ("d7vk", self.manager.supported_d7vk, "D7VK"),
            ("dxvk", self.manager.supported_dxvk, "DXVK"),
            ("vkd3d", self.manager.supported_vkd3d, "VKD3D"),
            ("nvapi", self.manager.supported_nvapi, "DXVK-NVAPI"),
            ("latencyflex", self.manager.supported_latencyflex, "LatencyFleX"),
        ]

        for component_type, supported_components, title in dll_components:
            expander = ComponentExpander(title)
            if self.__populate_component_list(
                component_type, supported_components, expander
            ):
                self.list_dlls.add(expander)
                self.__registry.append(expander)

    def __on_runner_expander_expanded(self, expander, _pspec, runner_struct):
        if not expander.get_expanded() or runner_struct["expanded"]:
            return
        for runner_data in runner_struct["expander_queue"]:
            _entry = ComponentEntry(
                self.window, runner_data, runner_struct["runner_type"]
            )
            expander.add_row(_entry)
            self.__registry.append(_entry)
        runner_struct["expanded"] = True

    def __populate_runners_helper(
        self, runner_type, supported_runners_dict, identifiable_runners_struct
    ):
        for identifiable_runner in identifiable_runners_struct:
            identifiable_runner["runner_type"] = runner_type

        offline_runners_list = self.manager.get_offline_components(runner_type)
        if self.__display_unstable_candidate():
            for offline_runner_name in offline_runners_list:
                offline_runner = [
                    offline_runner_name,
                    {
                        "Installed": True,
                        "Channel": "unstable",
                        "Category": "runners",
                        "Sub-category": "wine" if runner_type == "runner" else "proton",
                    },
                ]
                _runner_name = offline_runner_name.lower()
                for identifiable_runner in identifiable_runners_struct:
                    if _runner_name.startswith(identifiable_runner["prefix"]):
                        identifiable_runner["offline_runners"].append(offline_runner)
                        break

        for supported_runner in supported_runners_dict.items():
            _runner_name = supported_runner[0].lower()
            if not self.__display_unstable_candidate(supported_runner):
                continue

            for identifiable_runner in identifiable_runners_struct:
                if _runner_name.startswith(identifiable_runner["prefix"]):
                    while (
                        identifiable_runner["offline_runners"]
                        and sort_by_version(
                            [
                                identifiable_runner["offline_runners"][0][0],
                                supported_runner[0],
                            ]
                        )[0]
                        == identifiable_runner["offline_runners"][0][0]
                    ):
                        offline_runner = identifiable_runner["offline_runners"].pop(0)
                        identifiable_runner["expander_queue"].append(offline_runner)
                        identifiable_runner["count"] += 1
                    identifiable_runner["expander_queue"].append(supported_runner)
                    identifiable_runner["count"] += 1
                    break

        # Don't forget left over offline runners
        for identifiable_runner in identifiable_runners_struct:
            while identifiable_runner["offline_runners"]:
                offline_runner = identifiable_runner["offline_runners"].pop(0)
                identifiable_runner["expander_queue"].append(offline_runner)
                identifiable_runner["count"] += 1

    def populate_runners_list(self):
        exp_soda = ComponentExpander(
            "Soda",
            _("Based on Valve's Wine, includes Staging and Proton patches."),
            icon_name="soda-runner",
        )
        exp_caffe = ComponentExpander(
            "Caffe",
            _("Based on Wine upstream, includes Staging and Proton patches."),
            icon_name="caffe-runner",
        )
        exp_wine_ge = ComponentExpander(
            "wine-GE",
            _("Unmaintained. Wine-GE has been archived in favor of umu-launcher."),
        )
        exp_kron4ek = ComponentExpander(
            "Kron4ek",
            _(
                "Based on Wine upstream, Staging, Staging-TkG and Proton patchset optionally available."
            ),
        )
        exp_lutris = ComponentExpander("Lutris", _("Unmaintained legacy runners."))
        exp_vaniglia = ComponentExpander(
            "Vaniglia",
            _("Based on Wine upstream, includes Staging patches."),
            icon_name="vaniglia-runner",
        )
        exp_protosoda = ComponentExpander(
            "ProtoSoda",
            _("Soda adapted for Proton and UMU."),
            icon_name="protosoda-runner",
        )
        exp_proton_ge = ComponentExpander(
            "proton-GE",
            _(
                "Based on most recent bleeding-edge Valve's Proton Experimental, "
                "includes Staging and custom patches. "
                "Using the Steam Runtime is recommended."
            ),
        )
        exp_proton_cachyos = ComponentExpander(
            "Proton CachyOS",
            _("CachyOS Proton builds. Using the Steam Runtime is recommended."),
        )
        exp_other_wine = ComponentExpander(_("Other Wine runners"))
        exp_other_proton = ComponentExpander(_("Other Proton runners"))

        identifiable_wine_runners = [
            {
                "prefix": "soda",
                "count": 0,
                "expander": exp_soda,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
            {
                "prefix": "caffe",
                "count": 0,
                "expander": exp_caffe,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
            {
                "prefix": "vaniglia",
                "count": 0,
                "expander": exp_vaniglia,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
            {
                "prefix": "kron4ek",
                "count": 0,
                "expander": exp_kron4ek,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
        ]
        deprecated_wine_runners = [
            {
                "prefix": "wine-ge",
                "count": 0,
                "expander": exp_wine_ge,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
            {
                "prefix": "lutris",
                "count": 0,
                "expander": exp_lutris,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
        ]
        identifiable_proton_runners = [
            {
                "prefix": "protosoda",
                "count": 0,
                "expander": exp_protosoda,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
            {
                "prefix": "proton-cachyos",
                "count": 0,
                "expander": exp_proton_cachyos,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
            {
                "prefix": "ge-proton",
                "count": 0,
                "expander": exp_proton_ge,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
        ]
        other_wine_runners = [
            {
                "prefix": "",
                "count": 0,
                "expander": exp_other_wine,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
        ]
        other_proton_runners = [
            {
                "prefix": "",
                "count": 0,
                "expander": exp_other_proton,
                "offline_runners": [],
                "expander_queue": [],
                "expanded": False,
            },
        ]

        self.__populate_runners_helper(
            "runner",
            self.manager.supported_wine_runners,
            identifiable_wine_runners + deprecated_wine_runners + other_wine_runners,
        )
        self.__populate_runners_helper(
            "runner:proton",
            self.manager.supported_proton_runners,
            identifiable_proton_runners + other_proton_runners,
        )

        for runner in (
            identifiable_wine_runners[:3]
            + identifiable_proton_runners[:1]
            + identifiable_wine_runners[3:]
            + identifiable_proton_runners[1:]
            + other_wine_runners
            + other_proton_runners
            + deprecated_wine_runners
        ):
            if runner["count"] > 0:
                self.list_runners.add(runner["expander"])
                self.__registry.append(runner["expander"])
                runner["expander"].connect(
                    "notify::expanded",
                    self.__on_runner_expander_expanded,
                    runner,
                )

        self.installers_stack.set_visible_child_name("installers_list")

    def populate_cache_list(self):
        self.cache_stack.set_visible_child_name("cache_loading")
        self.cache_spinner.start()

        def update_cache_view(result, error=False):
            self.cache_spinner.stop()
            if error or result is None:
                return

            self.cache_stack.set_visible_child_name("cache_list")
            self.__render_cache_details(result)

        RunAsync(task_func=self.manager.get_cache_details, callback=update_cache_view)

    def __render_cache_details(self, cache_details: dict):
        temp_cache = cache_details.get("temp", {})
        templates_cache = cache_details.get("templates", [])
        templates_size = cache_details.get("templates_size", "0B")
        total_size = cache_details.get("total_size", "0B")

        self.label_cache_total_size.set_label(total_size)
        self.label_cache_temp_size.set_label(temp_cache.get("size", "0B"))
        self.label_cache_templates_size.set_label(templates_size)

        has_any_cache = cache_details.get("total_size_bytes", 0) > 0
        has_temp_cache = temp_cache.get("size_bytes", 0) > 0
        has_templates_cache = cache_details.get("templates_size_bytes", 0) > 0

        self.btn_cache_clear_all.set_sensitive(has_any_cache)
        self.btn_cache_clear_temp.set_sensitive(has_temp_cache)
        self.btn_cache_clear_templates.set_sensitive(has_templates_cache)

        self.__populate_template_cache_rows(templates_cache)

    def __populate_template_cache_rows(self, templates: list[dict]):
        for row in self.__cache_registry:
            parent = row.get_parent()
            if parent:
                parent.remove(row)
        self.__cache_registry = []

        if not templates:
            empty_row = Adw.ActionRow()
            empty_row.set_title(_("No templates cached yet."))
            empty_row.set_subtitle(
                _(
                    "Templates are created after you make the first bottle for each environment."
                )
            )
            empty_row.set_activatable(False)
            empty_row.set_can_focus(False)
            empty_row.set_sensitive(False)
            self.template_cache_group.add(empty_row)
            self.__cache_registry.append(empty_row)
            return

        for template in templates:
            row = Adw.ActionRow()
            row.set_title(self.__format_template_title(template))
            row.set_subtitle(self.__format_template_subtitle(template))
            row.set_activatable(False)
            row.set_can_focus(False)

            size_label = Gtk.Label(label=template.get("size", "0B"))
            size_label.set_xalign(1.0)
            size_label.get_style_context().add_class("dim-label")
            row.add_suffix(size_label)

            btn_remove = Gtk.Button.new_with_label(_("_Delete"))
            btn_remove.set_use_underline(True)
            btn_remove.set_valign(Gtk.Align.CENTER)
            btn_remove.add_css_class("destructive-action")
            btn_remove.connect("clicked", self.__confirm_clear_template, template)
            row.add_suffix(btn_remove)

            self.template_cache_group.add(row)
            self.__cache_registry.append(row)

    def __format_template_title(self, template: dict) -> str:
        env_label = self.__format_env_label(template.get("env", ""))
        return _("%s template") % env_label

    def __format_template_subtitle(self, template: dict) -> str:
        created = template.get("created", "")
        env_label = self.__format_env_label(template.get("env", ""))

        if created:
            return _("Cached prefix for the %s environment, created on %s") % (
                env_label,
                created,
            )

        return _("Cached prefix for the %s environment") % env_label

    def __format_env_label(self, env: str) -> str:
        env_labels = {
            "gaming": _("Gaming"),
            "application": _("Software"),
        }

        env_value = (env or "").lower()

        if env_value in env_labels:
            return env_labels.get(env_value, env.title())

        return env.title() if env else _("Unknown")

    def __confirm_clear_all_caches(self, widget):
        widget.set_sensitive(False)
        self.__confirm_cache_action(
            title=_("Delete all caches?"),
            description=_(
                "Removing every cache will make Bottles re-download resources and rebuild templates, which can take longer."
            ),
            action=self.manager.clear_all_caches,
            button=widget,
        )

    def __confirm_clear_temp_cache(self, widget):
        widget.set_sensitive(False)
        self.__confirm_cache_action(
            title=_("Delete temp cache?"),
            description=_(
                "Clearing the temp cache removes downloaded archives and extracted files, so future installs may take longer."
            ),
            action=self.manager.clear_temp_cache,
            button=widget,
        )

    def __confirm_clear_templates_cache(self, widget):
        widget.set_sensitive(False)
        self.__confirm_cache_action(
            title=_("Delete all prefix templates?"),
            description=_(
                "Removing all prefix templates will slow down the next bottle creation while Bottles rebuilds them."
            ),
            action=self.manager.clear_templates_cache,
            button=widget,
        )

    def __confirm_clear_template(self, widget, template: dict):
        widget.set_sensitive(False)
        env_label = self.__format_env_label(template.get("env", ""))
        title = _("Delete the %s template?") % env_label
        description = _(
            "The next bottle for this environment will take longer to create because Bottles must rebuild the template."
        )

        self.__confirm_cache_action(
            title=title,
            description=description,
            action=lambda: self.manager.clear_template_cache(template.get("uuid", "")),
            button=widget,
        )

    def __confirm_cache_action(self, title: str, description: str, action, button=None):
        dialog = Adw.MessageDialog.new(
            self.window,
            title,
            description,
        )
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("delete", _("_Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_response(dlg, response):
            dlg.destroy()
            if response != "delete":
                if button:
                    button.set_sensitive(True)
                return

            RunAsync(
                task_func=action,
                callback=lambda result, error=False: self.__cache_action_finished(
                    result, button
                ),
            )

        dialog.connect("response", handle_response)
        dialog.present()

    def __cache_action_finished(self, result, button=None):
        if button:
            button.set_sensitive(True)

        self.populate_cache_list()
