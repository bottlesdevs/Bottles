# ruff: noqa: E402

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from gi.repository import Gio

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.backend.utils.manager import ManagerUtils
from bottles.frontend.utils.common import format_runner_name, get_runner_icon_name
from bottles.frontend.views.bottle_preferences import PreferencesView


@pytest.mark.parametrize(
    ("runner", "expected"),
    [
        ("sys-wine-11.0", "Built-in Wine 11.0"),
        ("soda-11.0-3", "soda-11.0-3"),
    ],
)
def test_flatpak_runner_name(monkeypatch, runner, expected):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")

    assert format_runner_name(runner) == expected


def test_native_system_runner_name_is_unchanged(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)

    assert format_runner_name("sys-wine-11.0") == "sys-wine-11.0"


@pytest.mark.parametrize(
    ("runner", "expected"),
    [
        ("soda-11.0-4", "soda-runner"),
        ("Caffe-9.7", "caffe-runner"),
        ("vaniglia-8.0", "vaniglia-runner"),
        ("protosoda-11.1-2", "protosoda-runner"),
        ("GE-Proton10-20", None),
        ("sys-wine-11.0", None),
    ],
)
def test_runner_icon_name(runner, expected):
    assert get_runner_icon_name(runner) == expected


def test_runner_dropdown_uses_display_names_without_changing_ids(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(ManagerUtils, "get_languages", lambda: [])
    manager = SimpleNamespace(
        runners_available=["soda-11.0-3", "sys-wine-11.0"],
        dxvk_available=[],
        vkd3d_available=[],
        nvapi_available=[],
        latencyflex_available=[],
    )
    view = SimpleNamespace(manager=manager)
    for name in (
        "runner",
        "dxvk",
        "vkd3d",
        "nvapi",
        "latencyflex",
        "language",
        "windows",
    ):
        setattr(view, f"combo_{name}", Mock())
        setattr(view, f"_PreferencesView__set_{name}", Mock())
    for name in (
        "runner",
        "dxvk",
        "vkd3d",
        "nvapi",
        "latencyflex",
        "languages",
        "windows",
    ):
        setattr(view, f"str_list_{name}", Mock())

    PreferencesView.update_combo_components(view)

    labels = [call.args[0] for call in view.str_list_runner.append.call_args_list]
    assert labels == ["soda-11.0-3", "Built-in Wine 11.0"]
    assert manager.runners_available[1] == "sys-wine-11.0"
