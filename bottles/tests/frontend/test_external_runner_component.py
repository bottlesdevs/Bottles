# ruff: noqa: E402

from types import SimpleNamespace

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.widgets.component import ComponentEntry  # noqa: E402


def test_external_runner_cannot_be_removed_from_bottles():
    Adw.init()
    component_manager = SimpleNamespace(is_in_use=lambda *_args: False)
    window = SimpleNamespace(
        manager=SimpleNamespace(
            component_manager=component_manager,
            external_runners={"GE-Proton10-4"},
            utils_conn=SimpleNamespace(status=True),
        )
    )

    entry = ComponentEntry(
        window,
        ["GE-Proton10-4", {"Installed": True}],
        "runner:proton",
    )

    assert entry.get_subtitle() == "Discovered in Steam"
    assert entry.btn_browse.get_visible()
    assert not entry.btn_remove.get_visible()
