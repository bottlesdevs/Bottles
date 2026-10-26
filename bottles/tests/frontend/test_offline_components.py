# ruff: noqa: E402
from types import MethodType, SimpleNamespace

import pytest
from gi.repository import Adw, Gio

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.views.preferences import PreferencesWindow


def _view(installed):
    Adw.init()
    manager = SimpleNamespace(
        get_offline_components=lambda *_args: installed,
        component_manager=SimpleNamespace(is_in_use=lambda *_args: False),
        external_runners=set(),
        utils_conn=SimpleNamespace(status=False),
    )
    view = SimpleNamespace(window=SimpleNamespace(
        manager=manager, settings=SimpleNamespace(get_boolean=lambda _key: False)
    ), manager=manager, _PreferencesWindow__registry=[])
    view._PreferencesWindow__display_unstable_candidate = MethodType(
        PreferencesWindow._PreferencesWindow__display_unstable_candidate, view
    )
    return view


def test_installed_dll_is_manageable_without_a_catalog():
    view = _view(["dxvk-2.7"])

    count = PreferencesWindow._PreferencesWindow__populate_component_list(
        view, "dxvk", {}, Adw.ExpanderRow()
    )

    assert count == 1
    entry = view._PreferencesWindow__registry[0]
    assert entry.get_title() == "dxvk-2.7"
    assert entry.btn_remove.get_visible()


def test_installed_runner_is_listed_without_a_catalog():
    view = _view(["soda-11.0-35-experimental"])
    runners = [{"prefix": "soda", "offline_runners": [], "expander_queue": [], "count": 0}]

    PreferencesWindow._PreferencesWindow__populate_runners_helper(view, "runner", {}, runners)

    assert runners[0]["count"] == 1
    assert runners[0]["expander_queue"][0][0] == "soda-11.0-35-experimental"


@pytest.mark.parametrize("installed", (True, False))
def test_installed_candidates_remain_visible_when_candidates_are_disabled(installed):
    view = _view([])

    shown = view._PreferencesWindow__display_unstable_candidate(
        ["dxvk-test", {"Channel": "unstable", "Installed": installed}]
    )

    assert shown is installed
