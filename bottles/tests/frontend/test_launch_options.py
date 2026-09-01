# ruff: noqa: E402
from types import SimpleNamespace

from gi.repository import Gio

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.windows.launchoptions import LaunchOptionsDialog


def test_arguments_toggle_disables_only_the_text_entry():
    editable = []
    dialog = SimpleNamespace(
        entry_arguments=SimpleNamespace(set_editable=editable.append),
        switch_arguments=SimpleNamespace(get_active=lambda: False),
    )

    LaunchOptionsDialog._LaunchOptionsDialog__toggle_arguments(dialog)

    assert editable == [False]
