# window.py
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

import contextlib
import os
import webbrowser
from datetime import datetime, timedelta
from gettext import gettext as _

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Xdp, XdpGtk4

from bottles.backend.globals import Paths
from bottles.backend.health import HealthChecker
from bottles.backend.logger import Logger
from bottles.backend.managers.data import DataManager, UserDataKeys
from bottles.backend.managers.journal import JournalManager
from bottles.backend.managers.library import LibraryManager
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import Notification, SignalManager, Signals
from bottles.backend.umu import UmuRepositoryError
from bottles.backend.utils.connection import ConnectionUtils
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.operation import TaskSyncer
from bottles.frontend.params import APP_ID, APP_MAJOR_VERSION, PROFILE
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.views.details import DetailsView
from bottles.frontend.views.importer import ImporterView
from bottles.frontend.views.library import LibraryView
from bottles.frontend.views.list import BottleView
from bottles.frontend.views.loading import LoadingView
from bottles.frontend.views.new_bottle_dialog import BottlesNewBottleDialog
from bottles.frontend.views.preferences import PreferencesWindow
from bottles.frontend.windows.crash import CrashReportDialog
from bottles.frontend.windows.depscheck import DependenciesCheckDialog
from bottles.frontend.windows.eagleintel import EagleIntelDialog
from bottles.frontend.windows.funding import FundingDialog
from bottles.frontend.windows.onboard import OnboardDialog
from bottles.frontend.windows.umu import (
    UmuAddGameDialog,
    UmuGameDialog,
    UmuInstallDialog,
    UmuSearchDialog,
)
from bottles.frontend.windows.winebridgeupdate import WineBridgeUpdateDialog

logging = Logger()


@Gtk.Template(resource_path="/com/usebottles/bottles/window.ui")
class BottlesWindow(Adw.ApplicationWindow):
    __gtype_name__ = "BottlesWindow"

    # region Widgets
    stack_main = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    btn_search = Gtk.Template.Child()
    btn_donate = Gtk.Template.Child()
    btn_noconnection = Gtk.Template.Child()
    banner_offline = Gtk.Template.Child()
    box_actions = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    view_switcher_title = Gtk.Template.Child()
    view_switcher_bar = Gtk.Template.Child()
    main_leaf = Gtk.Template.Child()
    toasts = Gtk.Template.Child()
    # endregion

    # Common variables
    previous_page = ""
    settings = Gio.Settings.new(APP_ID)
    argument_executed = False
    _winebridge_dialog_shown = False

    def __init__(self, arg_bottle, **kwargs):
        width = self.settings.get_int("window-width")
        height = self.settings.get_int("window-height")

        super().__init__(**kwargs, default_width=width, default_height=height)

        self.data_mgr = DataManager()
        self._show_eagle_intel_announcement = not self.data_mgr.get(
            UserDataKeys.EagleIntelAnnouncementSeen, False
        )
        self._show_funding = False
        self._funding_dialog = None

        show_funding_setting = self.settings.get_boolean("show-funding")
        dismissed = self.data_mgr.get(UserDataKeys.FundingDismissed, False)
        supporter = self.data_mgr.get(UserDataKeys.FundingSupporter, False)

        if show_funding_setting and not dismissed and not supporter:
            last_major = str(
                self.data_mgr.get(UserDataKeys.LastFundingMajor, "")
            )
            last_prompt = self.data_mgr.get(UserDataKeys.LastFundingPrompt, "")

            if last_major != str(APP_MAJOR_VERSION) or not last_prompt:
                self._show_funding = True
            else:
                try:
                    last_date = datetime.strptime(last_prompt, "%Y-%m-%d")
                    if datetime.now() - last_date >= timedelta(days=7):
                        self._show_funding = True
                except ValueError:
                    self._show_funding = True

        self.utils_conn = ConnectionUtils(
            force_offline=self.settings.get_boolean("force-offline")
        )
        self.manager = None
        self.arg_bottle = arg_bottle
        self._showing_onboard = False
        self._pending_crash_log = None
        self._show_custom_path_warning = False
        self._winebridge_prompt_attempts = 0
        self.app = kwargs.get("application")
        self.set_icon_name(APP_ID)

        if PROFILE == "development":
            self.add_css_class("devel")

        self.btn_donate.add_css_class("donate")
        self.__update_donate_button()

        # Set night theme according to user settings
        if self.settings.get_boolean("dark-theme"):
            manager = Adw.StyleManager.get_default()
            manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        # Be VERY explicit that non-sandboxed environments are unsupported
        if not os.environ.get("CPAK_CONTAINER_ID") and not Xdp.Portal.running_under_sandbox():

            def response(dialog, response, *args):
                if response == "close":
                    quit(1)

            body = _(
                "Bottles is only supported within a sandboxed environment. Official sources of Bottles are available at"
            )
            download_url = "usebottles.com/download"

            error_dialog = Adw.AlertDialog.new(
                _("Unsupported Environment"),
                f"{body} <a href='https://{download_url}' title='https://{download_url}'>{download_url}.</a>",
            )

            error_dialog.add_response("close", _("Close"))
            error_dialog.set_body_use_markup(True)
            error_dialog.connect("response", response)
            error_dialog.present(self)
            logging.error(
                _(
                    "Bottles is only supported within a sandboxed format. Official sources of Bottles are available at:"
                )
            )
            logging.error("https://usebottles.com/download/")
            return

        # Loading view
        self.page_loading = LoadingView()

        # Populate stack
        self.stack_main.add_named(
            child=self.page_loading, name="page_loading"
        ).set_visible(False)
        self.headerbar.add_css_class("flat")

        # Signal connections
        self.btn_donate.connect("clicked", self.__show_funding_dialog)
        self.btn_add.connect("clicked", self.show_add_view)
        self.btn_search.connect("toggled", self.__toggle_search)
        self.btn_noconnection.connect("clicked", self.check_for_connection)
        self.banner_offline.connect("button-clicked", self.check_for_connection)
        self.stack_main.connect("notify::visible-child", self.__on_page_changed)

        # backend signal handlers
        self.task_syncer = TaskSyncer(self)
        SignalManager.connect(Signals.TaskAdded, self.task_syncer.task_added_handler)
        SignalManager.connect(
            Signals.TaskRemoved, self.task_syncer.task_removed_handler
        )
        SignalManager.connect(
            Signals.TaskUpdated, self.task_syncer.task_updated_handler
        )
        SignalManager.connect(
            Signals.NetworkStatusChanged, self.network_changed_handler
        )
        SignalManager.connect(Signals.GNotification, self.g_notification_handler)
        SignalManager.connect(Signals.GShowUri, self.g_show_uri_handler)

        # keep the session awake while one or more programs are running
        self.__inhibit_cookie = 0
        self.__running_launches = set()
        SignalManager.connect(Signals.ProgramStarted, self.__on_program_started)
        SignalManager.connect(Signals.ProgramFinished, self.__on_program_finished)

        self.__on_start()
        logging.info(
            "Bottles Started!",
        )

    def __update_donate_button(self):
        supporter = self.data_mgr.get(UserDataKeys.FundingSupporter, False)
        self.btn_donate.set_label("")
        self.btn_donate.set_icon_name("heart-symbolic")
        self.btn_donate.set_tooltip_text(
            _("Thank you for supporting Bottles")
            if supporter
            else _("Support Bottles")
        )
        if supporter:
            self.btn_donate.add_css_class("supporter")
        else:
            self.btn_donate.remove_css_class("supporter")

    def __show_funding_dialog(self, *_args):
        if self._funding_dialog is not None:
            self._funding_dialog.present(self)
            return

        bottle_count = len(self.manager.local_bottles) if self.manager else 0
        self._funding_dialog = FundingDialog(self, bottle_count=bottle_count)
        self._funding_dialog.connect("response", self.__funding_response, False)
        self._funding_dialog.present(self)

    @Gtk.Template.Callback()
    def on_close_request(self, *args):
        self.settings.set_int("window-width", self.get_width())
        self.settings.set_int("window-height", self.get_height())

    # region Backend signal handlers
    @GtkUtils.run_in_main_loop
    def network_changed_handler(self, res: Result):
        self.banner_offline.set_revealed(not res.status)

    @GtkUtils.run_in_main_loop
    def g_notification_handler(self, res: Result):
        """handle backend notification request"""
        notify: Notification = res.data
        self.send_notification(title=notify.title, text=notify.text, image=notify.image)

    @GtkUtils.run_in_main_loop
    def g_show_uri_handler(self, res: Result):
        """handle backend show_uri request"""
        uri: str = res.data
        if "FLATPAK_ID" in os.environ:
            Xdp.Portal().open_uri(
                XdpGtk4.parent_new_gtk(self),
                uri,
                Xdp.OpenUriFlags.NONE,
                None,
                None,
            )
            return

        Gtk.show_uri(self, uri, Gdk.CURRENT_TIME)

    @GtkUtils.run_in_main_loop
    def __on_program_started(self, res: Result):
        """Inhibit session idle while a program is running, so the screen does
        not blank during controller-only gameplay."""
        launch_id = getattr(res.data, "launch_id", None)
        if launch_id is None:
            return
        self.__running_launches.add(launch_id)

        if self.__inhibit_cookie:
            return
        app = self.get_application()
        if app:
            self.__inhibit_cookie = app.inhibit(
                self,
                Gtk.ApplicationInhibitFlags.IDLE | Gtk.ApplicationInhibitFlags.SUSPEND,
                _("A program is running"),
            )

    @GtkUtils.run_in_main_loop
    def __on_program_finished(self, res: Result):
        launch_id = getattr(res.data, "launch_id", None)
        if launch_id is not None:
            self.__running_launches.discard(launch_id)

        if self.__running_launches or not self.__inhibit_cookie:
            return
        app = self.get_application()
        if app:
            app.uninhibit(self.__inhibit_cookie)
        self.__inhibit_cookie = 0

    # endregion

    def update_library(self):
        GLib.idle_add(self.page_library.update)

    def title(self, title, subtitle: str = ""):
        self.view_switcher_title.set_title(title)
        self.view_switcher_title.set_subtitle(subtitle)

    def check_for_connection(self, *_args):
        """
        This method checks if the client has an internet connection.
        If true, the manager checks will be performed, unlocking all the
        features locked for no internet connection. Runs off the main loop so
        the UI stays responsive and the component catalog is refetched, so the
        runners/components/dependencies tabs work again without a restart.
        """

        def task():
            if self.manager and self.utils_conn.check_connection():
                self.manager.checks(install_latest=False, first_run=True)

        RunAsync(task)

    def __maybe_prompt_winebridge_update(self):
        if self._winebridge_dialog_shown or self._showing_onboard:
            return

        if not self.manager:
            return

        if (
            not self.manager.supported_winebridge
            and self._winebridge_prompt_attempts < 5
        ):
            self._winebridge_prompt_attempts += 1
            GLib.timeout_add_seconds(1, self.__maybe_prompt_winebridge_update)
            return

        status = self.manager.winebridge_update_status()
        needs_update = status.get("needs_latest", False)
        missing = status.get("missing", False)
        latest = status.get("latest_supported")
        installed = status.get("installed_identifier")
        offline = not self.utils_conn.check_connection()

        if not (needs_update or missing):
            return

        self._winebridge_dialog_shown = True

        dialog = WineBridgeUpdateDialog(
            self,
            manager=self.manager,
            latest_version=latest,
            installed_version=installed,
            offline=offline,
        )
        dialog.present()

    def __on_start(self):
        """
        This method is called before the window is shown. This check if there
        is at least one local runner installed. If not, the user will be
        prompted with the onboard dialog.
        """

        @GtkUtils.run_in_main_loop
        def set_manager(result: Manager, error=None):
            self.manager = result

            tmp_runners = self.manager.get_managed_wine_runners()
            if len(tmp_runners) == 0:
                self._showing_onboard = True
                self.show_onboard_view()

            # Pages
            self.page_details = DetailsView(self)
            self.page_list = BottleView(self, arg_bottle=self.arg_bottle)
            self.page_importer = ImporterView(self)
            self.page_library = LibraryView(self)

            self.main_leaf.append(self.page_details)
            self.main_leaf.append(self.page_importer)

            self.main_leaf.get_page(self.page_details).set_navigatable(False)
            self.main_leaf.get_page(self.page_importer).set_navigatable(False)

            self.stack_main.add_titled(
                child=self.page_list, name="page_list", title=_("Bottles")
            ).set_icon_name(f"{APP_ID}-symbolic")
            self.stack_main.add_titled(
                child=self.page_library, name="page_library", title=_("Library")
            ).set_icon_name("library-symbolic")

            self.page_list.search_bar.set_key_capture_widget(self)
            self.page_library.search_bar.set_key_capture_widget(self)
            self.page_list.search_bar.connect(
                "notify::search-mode-enabled", self.__sync_search_button
            )
            self.page_library.search_bar.connect(
                "notify::search-mode-enabled", self.__sync_search_button
            )

            if (
                self.stack_main.get_child_by_name(
                    self.settings.get_string("startup-view")
                )
                is None
            ):
                self.stack_main.set_visible_child_name("page_list")

            self.settings.bind(
                "startup-view",
                self.stack_main,
                "visible-child-name",
                Gio.SettingsBindFlags.DEFAULT,
            )

            self.lock_ui(False)
            self.headerbar.get_style_context().remove_class("flat")

            user_defined_bottles_path = self.manager.data_mgr.get(
                UserDataKeys.CustomBottlesPath
            )
            self._show_custom_path_warning = bool(
                user_defined_bottles_path and Paths.bottles != user_defined_bottles_path
            )
            if not self._showing_onboard:
                GLib.idle_add(self.__continue_startup_dialogs)

        def get_manager():
            if self.utils_conn.check_connection():
                SignalManager.connect(
                    Signals.RepositoryFetched, self.page_loading.add_fetched
                )

            # do not redo connection if aborted connection
            mng = Manager(
                g_settings=self.settings,
                check_connection=self.utils_conn.aborted_connections == 0,
            )
            mng.get_umu_installation()
            return mng

        self.show_loading_view()
        RunAsync(get_manager, callback=set_manager)

        self.check_crash_log()

    def send_notification(self, title, text, image="", ignore_user=False):
        """
        This method is used to send a notification to the user using
        Gio.Notification. The notification is sent only if the
        user has enabled it in the settings. It is possible to ignore the
        user settings by passing the argument ignore_user=False.
        """
        if ignore_user or self.settings.get_boolean("notifications"):
            notification = Gio.Notification.new(title)
            notification.set_body(text)
            if image:
                icon = Gio.ThemedIcon.new(image)
                notification.set_icon(icon)

            self.props.application.send_notification(None, notification)

    def go_back(self, *_args):
        self.main_leaf.navigate(direction=Adw.NavigationDirection.BACK)

    def show_details_view(self, widget=False, config: BottleConfig | None = None):
        self.main_leaf.set_visible_child(self.page_details)
        self.page_details.set_config(config or BottleConfig())

    def show_loading_view(self, widget=False):
        self.lock_ui()
        self.stack_main.set_visible_child_name("page_loading")

    def show_onboard_view(self, widget=False):
        onboard_window = OnboardDialog(self)
        onboard_window.connect("closed", self.__on_onboard_closed)
        onboard_window.present(self)

    def __on_onboard_closed(self, _dialog):
        self._showing_onboard = False
        GLib.idle_add(self.__continue_startup_dialogs)

    def show_add_view(self, widget=False):
        if self.stack_main.get_visible_child_name() == "page_library":
            self.show_umu_search()
            return
        new_bottle_dialog = BottlesNewBottleDialog()
        new_bottle_dialog.present(self)

    def show_umu_add_game(self, _widget=False, mode="install"):
        if self.manager.get_umu_installation() is None:
            self.show_umu_unavailable()
            return
        if mode == "install":
            UmuInstallDialog(self).present(self)
            return
        UmuAddGameDialog(self, mode=mode).present(self)

    def show_umu_search(self, *_args, detected_prefix=None):
        if self.manager.get_umu_installation() is None:
            self.show_umu_unavailable()
            return
        UmuSearchDialog(self, detected_prefix=detected_prefix).present(self)

    def show_umu_game_settings(self, game_id):
        try:
            game = self.manager.umu_repository.load(game_id)
        except (FileNotFoundError, UmuRepositoryError) as error:
            self.show_toast(str(error))
            return
        UmuGameDialog(self, game).present(self)

    def show_umu_detected_prefix(self, entry):
        prefix = entry.get("path") if isinstance(entry, dict) else None
        if not prefix:
            return
        self.show_umu_search(detected_prefix=prefix)

    def launch_umu_installer(self, game):
        executor = self.manager.get_umu_executor()
        if executor is None:
            self.show_toast(
                _("UMU is not available. Check the UMU page in Preferences.")
            )
            return

        self.show_toast(_('Launching the installer for "{0}"...').format(game.name))

        def install():
            executor.run(game)
            GLib.idle_add(self.update_umu_views)
            return executor.wait(game) == 0

        @GtkUtils.run_in_main_loop
        def complete(success, error=False):
            updated = None
            try:
                current = self.manager.umu_repository.load(game.id)
                installer = current.extra.get("installer")
                state = "failed"
                if success:
                    state = (
                        "ready"
                        if installer and str(current.executable) != installer
                        else "draft"
                    )
                updated = self.manager.umu_repository.update(current, state=state)
                LibraryManager().sync_umu_game(updated)
            except (FileNotFoundError, UmuRepositoryError) as update_error:
                logging.warning(str(update_error))
            self.update_umu_views()
            if success and updated is not None:
                self.show_toast(
                    _(
                        "Installation finished. Select the installed game "
                        "executable in its settings."
                    )
                )
                UmuGameDialog(self, updated).present(self)
            else:
                self.show_toast(_("The installer did not finish successfully."))

        RunAsync(install, callback=complete)

    def update_umu_views(self):
        if hasattr(self, "page_list"):
            self.page_list.update_bottles_list(refresh_updates=False)
        if hasattr(self, "page_library"):
            self.page_library.update()

    def show_list_view(self, widget=False):
        self.stack_main.set_visible_child_name("page_list")

    def show_importer_view(self, widget=False):
        self.main_leaf.set_visible_child(self.page_importer)

    def show_prefs_view(self, widget=False, view=0, page=None):
        preferences_window = PreferencesWindow(self)
        if page:
            preferences_window.set_visible_page_name(page)
        elif view:
            pages = preferences_window.get_pages()
            if view < pages.get_n_items():
                preferences_window.set_visible_page(pages.get_item(view))
        preferences_window.present(self)

    def show_umu_preferences(self, *_args):
        self.show_prefs_view(page="umu")

    def show_umu_unavailable(self, *_args):
        self.show_toast(
            _("The UMU launcher is not available."),
            action_label=_("Preferences"),
            action_callback=self.show_umu_preferences,
        )

    def show_download_preferences_view(self, widget=False):
        self.show_prefs_view(widget, view=1)

    def show_runners_preferences_view(self, widget=False):
        self.show_prefs_view(widget, view=2)

    def check_crash_log(self):
        xdg_data_home = GLib.get_user_data_dir()
        log_path = f"{xdg_data_home}/bottles/crash.log"

        with contextlib.suppress(FileNotFoundError):
            with open(log_path, "r") as log_file:
                crash_log = log_file.readlines()
                os.remove(log_path)

            if crash_log:
                self._pending_crash_log = crash_log

    def __continue_startup_dialogs(self):
        if self._pending_crash_log:
            crash_log = self._pending_crash_log
            self._pending_crash_log = None
            dialog = CrashReportDialog(self, crash_log)
            dialog.connect("close-request", self.__crash_report_closed)
            dialog.present()
            return

        if self._show_custom_path_warning:
            self._show_custom_path_warning = False
            dialog = Adw.MessageDialog.new(
                self,
                _("Custom Bottles Path not Found"),
                _(
                    "Falling back to default path. No bottles from the given path will be listed."
                ),
            )
            dialog.add_response("cancel", _("_Dismiss"))
            dialog.connect("response", self.__custom_path_response)
            dialog.present()
            return

        self.__maybe_show_eagle_intel_dialog()

    def __crash_report_closed(self, _dialog):
        GLib.idle_add(self.__continue_startup_dialogs)

    def __custom_path_response(self, _dialog, _response):
        GLib.idle_add(self.__maybe_show_eagle_intel_dialog)

    def __maybe_show_funding_dialog(self):
        if not self._show_funding:
            GLib.idle_add(self.__maybe_prompt_winebridge_update)
            return

        self._show_funding = False
        count = self.data_mgr.get(UserDataKeys.FundingPromptCount) or 0
        self.data_mgr.set(UserDataKeys.FundingPromptCount, count + 1)

        today = datetime.now().strftime("%Y-%m-%d")
        self.data_mgr.set(UserDataKeys.LastFundingPrompt, today)
        self.data_mgr.set(UserDataKeys.LastFundingMajor, str(APP_MAJOR_VERSION))

        bottle_count = len(self.manager.local_bottles) if self.manager else 0
        dialog = FundingDialog(
            self,
            bottle_count=bottle_count,
            show_dont_show=count >= 7,
        )
        self._funding_dialog = dialog
        dialog.connect("response", self.__funding_response, True)
        dialog.present(self)

    def __maybe_show_eagle_intel_dialog(self):
        if not self._show_eagle_intel_announcement:
            self.__maybe_show_funding_dialog()
            return

        self._show_eagle_intel_announcement = False
        dialog = EagleIntelDialog(self)
        dialog.connect("response", self.__eagle_intel_response)
        dialog.present(self)

    def __eagle_intel_response(self, dialog, _response):
        self.data_mgr.set(UserDataKeys.EagleIntelAnnouncementSeen, True)
        GLib.idle_add(self.__maybe_show_funding_dialog)

    def __funding_response(self, dialog, response, continue_startup):
        if response == "dismiss":
            self.data_mgr.set(UserDataKeys.FundingDismissed, True)
            self.settings.set_boolean("show-funding", False)
        elif response == "supporter":
            self.data_mgr.set(UserDataKeys.FundingSupporter, True)
            self.data_mgr.set(UserDataKeys.FundingDismissed, True)
            self.settings.set_boolean("show-funding", False)
            self.__update_donate_button()

        self._funding_dialog = None
        if continue_startup:
            GLib.idle_add(self.__maybe_prompt_winebridge_update)

    def toggle_selection_mode(self, status: bool = True):
        context = self.headerbar.get_style_context()
        if status:
            context.add_class("selection-mode")
        else:
            context.remove_class("selection-mode")

    def lock_ui(self, status: bool = True):
        widgets = [
            self.btn_add,
            self.view_switcher_title,
        ]
        if self.btn_noconnection.get_visible():
            widgets.append(self.btn_noconnection)
        for w in widgets:
            w.set_visible(not status)

    def show_toast(
        self,
        message,
        timeout=3,
        action_label=None,
        action_callback=None,
        dismissed_callback=None,
    ) -> None:
        toast = Adw.Toast.new(message)
        toast.props.timeout = timeout

        if action_label and action_callback:
            toast.set_button_label(action_label)

            def wrapper_callback(*args):
                action_callback(toast)
                if dismissed_callback:
                    toast.handler_block_by_func(dismissed_callback)

            toast.connect("button-clicked", wrapper_callback)

        if dismissed_callback:
            toast.connect("dismissed", dismissed_callback)

        self.toasts.add_toast(toast)

    def __on_page_changed(self, stack, *args):
        page = stack.get_visible_child_name()
        is_bottles_list = page == "page_list"
        if hasattr(self, "page_list"):
            self.page_list.search_bar.set_search_mode(False)
            self.page_library.search_bar.set_search_mode(False)
        self.btn_search.set_active(False)
        self.btn_search.set_visible(page in ("page_list", "page_library"))
        self.btn_add.set_tooltip_text(
            _("Create New Bottle") if is_bottles_list else _("Add a Windows Game")
        )

    def __toggle_search(self, button):
        if not hasattr(self, "page_list"):
            return
        page = self.stack_main.get_visible_child_name()
        active = button.get_active()
        self.page_list.search_bar.set_search_mode(active and page == "page_list")
        self.page_library.search_bar.set_search_mode(
            active and page == "page_library"
        )

    def __sync_search_button(self, search_bar, *_args):
        page = self.stack_main.get_visible_child_name()
        if page not in ("page_list", "page_library"):
            return
        current = (
            self.page_list.search_bar
            if page == "page_list"
            else self.page_library.search_bar
        )
        if search_bar is current:
            self.btn_search.set_active(search_bar.get_search_mode())

    @staticmethod
    def proper_close():
        """Properly close Bottles"""
        quit()

    @staticmethod
    def open_url(widget, url):
        webbrowser.open_new_tab(url)
