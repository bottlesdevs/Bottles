# ruff: noqa: E402

from pathlib import Path
from types import SimpleNamespace

import pytest
from gi.repository import Gio

resource_path = Path("/app/share/bottles/bottles.gresource")
if not resource_path.exists():
    pytest.skip(
        "Bulk update tests require the Bottles Flatpak runtime",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))

from bottles.frontend.windows.bulkupdate import BottlesBulkUpdateDialog


@pytest.mark.parametrize(
    ("update", "expected"),
    [
        (
            {
                "id": "runner",
                "component_type": "runner:proton",
                "current": "ge-proton11-1",
                "latest": "ge-proton11-3",
            },
            ("runner:proton", "ge-proton11-1"),
        ),
        (
            {"id": "dxvk", "current": "dxvk-3.0", "latest": "dxvk-3.0.2"},
            ("dxvk", "dxvk-3.0"),
        ),
        (
            {
                "id": "winebridge",
                "current": "winebridge-1",
                "latest": "winebridge-2",
            },
            None,
        ),
    ],
)
def test_cleanup_target(update, expected):
    assert (
        BottlesBulkUpdateDialog._BottlesBulkUpdateDialog__cleanup_target(update)
        == expected
    )


def test_bulk_update_removes_each_unused_old_component_once(monkeypatch):
    removed = []
    component_manager = SimpleNamespace(
        uninstall=lambda component_type, name: removed.append((component_type, name))
        or SimpleNamespace(ok=True)
    )
    manager = SimpleNamespace(
        component_manager=component_manager,
        apply_component_update=lambda config, _update: SimpleNamespace(
            ok=True, data={"config": config}
        ),
    )
    view = SimpleNamespace(
        manager=manager,
        _BottlesBulkUpdateDialog__set_progress=lambda *_args: None,
        _BottlesBulkUpdateDialog__cleanup_target=(
            BottlesBulkUpdateDialog._BottlesBulkUpdateDialog__cleanup_target
        ),
    )
    update = {
        "id": "dxvk",
        "title": "DXVK",
        "current": "dxvk-3.0",
        "latest": "dxvk-3.0.2",
    }
    jobs = [
        ("one", SimpleNamespace(Name="One"), [update]),
        ("two", SimpleNamespace(Name="Two"), [update]),
    ]
    monkeypatch.setattr(
        "bottles.frontend.windows.bulkupdate.GLib.idle_add", lambda *_args: None
    )

    result = BottlesBulkUpdateDialog._BottlesBulkUpdateDialog__run_updates(
        view, jobs, remove_old=True
    )

    assert result == {"ok": 2, "failed": 0, "removed": 1}
    assert removed == [("dxvk", "dxvk-3.0")]
