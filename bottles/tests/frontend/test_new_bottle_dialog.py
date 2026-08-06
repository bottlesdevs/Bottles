# ruff: noqa: E402

from types import SimpleNamespace

import pytest
from gi.repository import Gio

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.frontend.views import new_bottle_dialog
from bottles.frontend.views.new_bottle_dialog import BottlesNewBottleDialog

INVALID_LIST_POSITION = 4294967295


def _make_dialog(runners, dxvks, selected=0):
    return SimpleNamespace(
        set_can_close=lambda _value: None,
        stack_create=SimpleNamespace(set_visible_child_name=lambda _name: None),
        _cancel_requested=None,
        _cleanup_config=None,
        _BottlesNewBottleDialog__reset_creation_steps=lambda: None,
        _BottlesNewBottleDialog__clear_creation_task=lambda: None,
        btn_cancel_creating=SimpleNamespace(
            set_sensitive=lambda _value: None,
            set_label=lambda _label: None,
        ),
        combo_runner=SimpleNamespace(get_selected=lambda: selected),
        combo_arch=SimpleNamespace(get_selected=lambda: 0),
        switch_sandbox=SimpleNamespace(get_active=lambda: False),
        entry_name=SimpleNamespace(get_text=lambda: "Bottle"),
        manager=SimpleNamespace(
            runners_available=runners,
            dxvk_available=dxvks,
            create_bottle=lambda **_kwargs: None,
        ),
        arch={"win64": "64-bit"},
        custom_path="",
        selected_environment="gaming",
        env_recipe_path=None,
        runner=None,
        update_output=lambda _text: None,
        finish=lambda *_args, **_kwargs: None,
        _creation_task=None,
        _creation_cancel_event=None,
        _creation_job=None,
    )


@pytest.fixture
def captured(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        new_bottle_dialog,
        "RunAsync",
        lambda **kwargs: calls.update(kwargs) or SimpleNamespace(),
    )
    monkeypatch.setattr(
        new_bottle_dialog,
        "Task",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        new_bottle_dialog.TaskManager,
        "add",
        staticmethod(lambda _task: None),
    )
    return calls


@pytest.mark.parametrize(
    ("runners", "dxvks", "selected", "expected_runner", "expected_dxvk"),
    (
        (["soda-11.0-4"], ["dxvk-2.7"], 0, "soda-11.0-4", "dxvk-2.7"),
        ([], [], INVALID_LIST_POSITION, False, False),
        (["soda-11.0-4"], [], 0, "soda-11.0-4", False),
        ([], ["dxvk-2.7"], INVALID_LIST_POSITION, False, "dxvk-2.7"),
    ),
)
def test_create_bottle_tolerates_missing_components(
    captured, runners, dxvks, selected, expected_runner, expected_dxvk
):
    dialog = _make_dialog(runners, dxvks, selected)

    BottlesNewBottleDialog.create_bottle(dialog)

    assert captured["runner"] == expected_runner
    assert captured["dxvk"] == expected_dxvk
