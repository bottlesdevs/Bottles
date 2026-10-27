# ruff: noqa: E402

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from gi.repository import Adw, Gio

from bottles.backend.models.result import Result

resource_path = Path(
    os.environ.get("BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource")
)
if not resource_path.exists():
    pytest.skip(
        "Preferences frontend tests require the Bottles resource bundle",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))

from bottles.frontend import params

params.APP_ID = "com.usebottles.bottles"

from bottles.frontend.windows import window as window_module
from bottles.frontend.windows.window import BottlesWindow
from bottles.frontend.views.preferences import PreferencesWindow
from bottles.frontend.widgets.component import ComponentEntry


class PreferencesWindowStub:
    instances = []

    def __init__(self, window):
        self.window = window
        self.page_name = None
        self.presented_with = None
        self.usage_refreshes = 0
        self.instances.append(self)

    def refresh_component_usage(self):
        self.usage_refreshes += 1

    def set_visible_page_name(self, page):
        self.page_name = page

    def present(self, window):
        self.presented_with = window


def test_preferences_window_is_reused(monkeypatch):
    PreferencesWindowStub.instances = []
    monkeypatch.setattr(window_module, "PreferencesWindow", PreferencesWindowStub)
    window = SimpleNamespace(_preferences_window=None)

    BottlesWindow.show_prefs_view(window)
    BottlesWindow.show_prefs_view(window, page="umu")

    assert len(PreferencesWindowStub.instances) == 1
    assert window._preferences_window.page_name == "umu"
    assert window._preferences_window.presented_with is window
    assert window._preferences_window.usage_refreshes == 2


def test_reopening_preferences_updates_runner_usage():
    Adw.init()
    active = {"wine-old"}
    window = SimpleNamespace(manager=SimpleNamespace(
        component_manager=SimpleNamespace(is_in_use=lambda _kind, name: name in active),
        external_runners=set(),
        utils_conn=SimpleNamespace(status=True),
    ))
    entries = [
        ComponentEntry(window, [name, {"Installed": True}], "runner")
        for name in ("wine-old", "wine-new")
    ]
    preferences = SimpleNamespace(
        _PreferencesWindow__registry=entries,
        present=Mock(),
    )
    preferences.refresh_component_usage = lambda: PreferencesWindow.refresh_component_usage(
        preferences
    )
    window._preferences_window = preferences
    assert not entries[0].btn_remove.get_visible()
    assert entries[1].btn_remove.get_visible()
    active.clear()
    active.add("wine-new")

    BottlesWindow.show_prefs_view(window)

    assert entries[0].btn_remove.get_visible()
    assert not entries[1].btn_remove.get_visible()


@pytest.mark.parametrize(
    ("force_offline", "online", "revealed"),
    [
        (True, False, False),
        (False, False, True),
        (False, True, False),
    ],
)
def test_offline_banner_respects_forced_offline_mode(force_offline, online, revealed):
    banner = Mock()
    window = SimpleNamespace(
        settings=SimpleNamespace(
            get_boolean=lambda key: force_offline if key == "force-offline" else False
        ),
        banner_offline=banner,
    )

    BottlesWindow.network_changed_handler.__wrapped__(window, Result(online))

    banner.set_revealed.assert_called_once_with(revealed)
