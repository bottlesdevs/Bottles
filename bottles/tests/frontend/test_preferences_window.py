# ruff: noqa: E402

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from gi.repository import Gio

resource_path = Path(
    os.environ.get("BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource")
)
if not resource_path.exists():
    pytest.skip(
        "Preferences frontend tests require the Bottles resource bundle",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))

from bottles.frontend.windows import window as window_module
from bottles.frontend.windows.window import BottlesWindow


class PreferencesWindowStub:
    instances = []

    def __init__(self, window):
        self.window = window
        self.page_name = None
        self.presented_with = None
        self.instances.append(self)

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
